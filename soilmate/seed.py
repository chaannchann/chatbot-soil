import json
import os
import sys

from db import db_cursor
from soil_catalog import SOILS_PATH, normalize_name

CROPS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "crops.json")

UPSERT_SOIL = """
    INSERT INTO soil_types (
        name, description, drainage, water_retention,
        common_ph_range, improvement_tips
    )
    VALUES (
        %(name)s, %(description)s, %(drainage)s, %(water_retention)s,
        %(common_ph_range)s, %(improvement_tips)s
    )
    ON CONFLICT (name) DO UPDATE SET
        description = EXCLUDED.description,
        drainage = EXCLUDED.drainage,
        water_retention = EXCLUDED.water_retention,
        common_ph_range = EXCLUDED.common_ph_range,
        improvement_tips = EXCLUDED.improvement_tips
    RETURNING id, name
"""

UPDATE_SOIL = """
    UPDATE soil_types SET
        name = %(name)s,
        description = %(description)s,
        drainage = %(drainage)s,
        water_retention = %(water_retention)s,
        common_ph_range = %(common_ph_range)s,
        improvement_tips = %(improvement_tips)s
    WHERE id = %(id)s
"""

UPSERT_CROP = """
    INSERT INTO crops (
        common_name, local_name, category, ph_min, ph_max,
        germination_days_min, germination_days_max,
        harvest_days_min, harvest_days_max, ideal_planting_season
    )
    VALUES (
        %(common_name)s, %(local_name)s, %(category)s, %(ph_min)s, %(ph_max)s,
        %(germination_days_min)s, %(germination_days_max)s,
        %(harvest_days_min)s, %(harvest_days_max)s, %(ideal_planting_season)s
    )
    ON CONFLICT (common_name) DO UPDATE SET
        local_name = EXCLUDED.local_name,
        category = EXCLUDED.category,
        ph_min = EXCLUDED.ph_min,
        ph_max = EXCLUDED.ph_max,
        germination_days_min = EXCLUDED.germination_days_min,
        germination_days_max = EXCLUDED.germination_days_max,
        harvest_days_min = EXCLUDED.harvest_days_min,
        harvest_days_max = EXCLUDED.harvest_days_max,
        ideal_planting_season = EXCLUDED.ideal_planting_season
    RETURNING id
"""


def load_catalog():
    with open(CROPS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)

    crops = data.get("crops", [])
    names = [crop["common_name"] for crop in crops]
    duplicates = {name for name in names if names.count(name) > 1}
    if duplicates:
        raise SystemExit(f"Duplicate crop names in crops.json: {sorted(duplicates)}")

    for crop in crops:
        bad_months = [m for m in crop.get("months", []) if not 1 <= int(m) <= 12]
        if bad_months:
            raise SystemExit(f"{crop['common_name']}: invalid months {bad_months}")
        if not crop.get("months"):
            raise SystemExit(f"{crop['common_name']}: no planting months defined")

    return crops


def load_soils():
    with open(SOILS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)

    soils = data.get("soils", [])
    required = {
        "class_key", "name", "description", "drainage",
        "water_retention", "common_ph_range", "improvement_tips",
    }

    seen_classes = set()
    seen_names = set()
    for soil in soils:
        missing = required - set(soil)
        if missing:
            raise SystemExit(f"{soil.get('name', '?')}: missing fields {sorted(missing)}")
        if soil["class_key"] in seen_classes:
            raise SystemExit(f"Duplicate soil class_key: {soil['class_key']}")
        if soil["name"] in seen_names:
            raise SystemExit(f"Duplicate soil name: {soil['name']}")
        seen_classes.add(soil["class_key"])
        seen_names.add(soil["name"])

    return soils


def seed_soils(cur, soils):
    """Insert/refresh profiles and rename legacy raw class-key rows in place.

    Older databases stored names like ``concrete_surface``. Matching on
    normalized class keys lets us rename those rows instead of creating a
    duplicate profile and orphaning their crop compatibility links.
    """
    cur.execute("SELECT id, name FROM soil_types ORDER BY id")
    existing = [dict(row) for row in cur.fetchall()]

    for soil in soils:
        match_keys = {
            normalize_name(soil["class_key"]),
            normalize_name(soil["name"]),
            normalize_name(soil.get("display_name", "")),
        }
        match_keys.discard("")

        matches = [
            row for row in existing
            if normalize_name(row["name"]) in match_keys
        ]
        exact = next((row for row in matches if row["name"] == soil["name"]), None)
        target = exact or (matches[0] if matches else None)

        if target:
            cur.execute(UPDATE_SOIL, {**soil, "id": target["id"]})
            target["name"] = soil["name"]

            # If both an old and a new spelling existed, merge them.
            for duplicate in matches:
                if duplicate["id"] == target["id"]:
                    continue
                cur.execute(
                    """
                    INSERT INTO crop_soil_compatibility (crop_id, soil_type_id)
                    SELECT crop_id, %s
                    FROM crop_soil_compatibility
                    WHERE soil_type_id = %s
                    ON CONFLICT (crop_id, soil_type_id) DO NOTHING
                    """,
                    (target["id"], duplicate["id"]),
                )
                cur.execute("DELETE FROM soil_types WHERE id = %s", (duplicate["id"],))
                existing.remove(duplicate)
        else:
            cur.execute(UPSERT_SOIL, soil)
            existing.append(dict(cur.fetchone()))

    return len(soils)


def seed():
    crops = load_catalog()
    soils = load_soils()
    crop_names = {crop["common_name"] for crop in crops}

    with db_cursor(commit=True) as cur:
        # Needed for ON CONFLICT (common_name) to be idempotent.
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_crops_common_name ON crops (common_name)")

        seed_soils(cur, soils)

        cur.execute("SELECT name FROM soil_types")
        known_soils = {row["name"] for row in cur.fetchall()}

        for crop in crops:
            unknown = [s for s in crop.get("soils", []) if s not in known_soils]
            if unknown:
                raise SystemExit(
                    f"{crop['common_name']}: unknown soil type(s) {unknown}. "
                    f"Known: {sorted(known_soils)}"
                )

            cur.execute(UPSERT_CROP, crop)
            crop_id = cur.fetchone()["id"]

            months = sorted({int(m) for m in crop["months"]})
            cur.execute("DELETE FROM crop_planting_months WHERE crop_id = %s", (crop_id,))
            cur.executemany(
                "INSERT INTO crop_planting_months (crop_id, month) VALUES (%s, %s)",
                [(crop_id, month) for month in months],
            )

            cur.execute("DELETE FROM crop_soil_compatibility WHERE crop_id = %s", (crop_id,))
            cur.executemany(
                """
                INSERT INTO crop_soil_compatibility (crop_id, soil_type_id)
                SELECT %s, id FROM soil_types WHERE name = %s
                """,
                [(crop_id, soil) for soil in crop.get("soils", [])],
            )

        # Per-soil crop lists add the newer profiles without duplicating the
        # original crop-side mappings already kept in data/crops.json.
        for soil in soils:
            for crop_name in soil.get("crops", []):
                if crop_name not in crop_names:
                    raise SystemExit(
                        f"{soil['name']}: unknown crop {crop_name!r} in soils.json"
                    )
                cur.execute(
                    """
                    INSERT INTO crop_soil_compatibility (crop_id, soil_type_id)
                    SELECT c.id, s.id
                    FROM crops c, soil_types s
                    WHERE c.common_name = %s AND s.name = %s
                    ON CONFLICT (crop_id, soil_type_id) DO NOTHING
                    """,
                    (crop_name, soil["name"]),
                )

    return len(crops), len(soils)


def main():
    count, soil_count = seed()
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM crops")
        total = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM soil_types")
        total_soils = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM crop_planting_months")
        months = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM crop_soil_compatibility")
        links = cur.fetchone()["n"]

    print(f"Seeded {soil_count} soil profiles (catalog now holds {total_soils}).")
    print(f"Seeded {count} crops (catalog now holds {total}).")
    print(f"  planting-month rows: {months}")
    print(f"  soil-compatibility rows: {links}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001
        print(f"Seeding failed: {error}", file=sys.stderr)
        raise
