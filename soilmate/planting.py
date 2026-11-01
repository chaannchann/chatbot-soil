"""Philippine planting-calendar logic.

The current month is computed locally with a fixed UTC+8 offset (the
Philippines has no daylight saving), so no weather or time API is involved.
Crop suitability comes from the structured ``crop_planting_months`` table.
"""

from datetime import datetime, timedelta, timezone

from db import db_cursor
from soil_catalog import canonical_name, display_name_for

PH_TZ = timezone(timedelta(hours=8))

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def ph_now():
    """Current date/time in Philippine Standard Time (UTC+8)."""
    return datetime.now(PH_TZ)


def season_for(month):
    """Return the Philippine season label for a month number (1-12)."""
    if 6 <= month <= 11:
        return "Wet Season (Habagat)"
    if month in (12, 1, 2):
        return "Cool Dry Season (Amihan)"
    return "Hot Dry Season (Summer)"


def season_tip(month):
    if 6 <= month <= 11:
        return (
            "It's the rainy season — raise your beds, keep drainage clear, and "
            "watch for fungal disease. Water-tolerant and root crops do best now."
        )
    if month in (12, 1, 2):
        return (
            "These are the best vegetable months of the year — cool and dry, "
            "ideal for leafy greens and fruiting crops like pechay, ampalaya, and talong."
        )
    return (
        "This is the hottest stretch of the year — mulch heavily, water deeply "
        "early in the morning, and favour drought-tolerant crops."
    )


def crops_for_month(month, soil=None):
    """Return crops that can be planted in ``month`` (optionally soil-filtered)."""
    params = [month]
    soil_clause = ""
    if soil:
        soil = canonical_name(soil) or soil
        soil_clause = """
            AND EXISTS (
                SELECT 1
                FROM crop_soil_compatibility csc
                JOIN soil_types s ON s.id = csc.soil_type_id
                WHERE csc.crop_id = c.id AND s.name = %s
            )
        """
        params.append(soil)

    query = f"""
        SELECT DISTINCT
            c.id, c.common_name, c.local_name, c.category,
            c.ph_min, c.ph_max,
            c.germination_days_min, c.germination_days_max,
            c.harvest_days_min, c.harvest_days_max,
            c.ideal_planting_season
        FROM crops c
        JOIN crop_planting_months m ON m.crop_id = c.id
        WHERE m.month = %s
        {soil_clause}
        ORDER BY c.category, c.common_name
    """

    with db_cursor() as cur:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]


def plant_now(soil=None):
    """Build the full 'what can I plant now' payload for the current month."""
    now = ph_now()
    month = now.month

    canonical_soil = canonical_name(soil) or soil
    crops = crops_for_month(month, canonical_soil)
    filtered_by_soil = bool(canonical_soil)
    note = None

    if not crops and canonical_soil:
        # Nothing mapped to that soil this month - still be useful.
        crops = crops_for_month(month, None)
        filtered_by_soil = False
        note = (
            f"No crops in our database are mapped to {display_name_for(canonical_soil)} for "
            f"{MONTH_NAMES[month - 1]}, so here are all crops suited to this month."
        )

    return {
        "month": month,
        "month_name": MONTH_NAMES[month - 1],
        "year": now.year,
        "season": season_for(month),
        "season_tip": season_tip(month),
        "soil_type": display_name_for(canonical_soil) if canonical_soil else None,
        "filtered_by_soil": filtered_by_soil,
        "crops": crops,
        "note": note,
        "count": len(crops),
    }


def _crop_line(crop):
    days = ""
    if crop.get("harvest_days_min") and crop.get("harvest_days_max"):
        days = f" — harvest in {crop['harvest_days_min']}\u2013{crop['harvest_days_max']} days"
    local = f" ({crop['local_name']})" if crop.get("local_name") else ""
    return f"- **{crop['common_name']}**{local}{days}"


def format_planting_reply(result):
    """Render a plant_now() result as a chat-friendly markdown message."""
    month_name = result["month_name"]
    season = result["season"]

    if not result["crops"]:
        return (
            f"I don't have crops listed for **{month_name}** ({season}) yet.\n\n"
            "Try uploading a soil photo and I'll at least tell you what your soil "
            "can support. More crops are being added to the calendar."
        )

    lines = [
        f"Here's what you can plant in **{month_name} {result['year']}** — "
        f"{season} in the Philippines:\n"
    ]

    if result["soil_type"] and result["filtered_by_soil"]:
        lines.append(f"Filtered for your **{result['soil_type']}**:\n")

    lines.extend(_crop_line(crop) for crop in result["crops"])

    if result.get("note"):
        lines.append(f"\n_{result['note']}_")

    lines.append(f"\n**Season tip:** {result['season_tip']}")
    lines.append("\nClick the *What can I plant this month?* chip any time to refresh this list.")
    return "\n".join(lines)
