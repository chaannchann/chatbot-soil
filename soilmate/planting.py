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
MONTH_NAMES_TL = [
    "Enero", "Pebrero", "Marso", "Abril", "Mayo", "Hunyo",
    "Hulyo", "Agosto", "Setyembre", "Oktubre", "Nobyembre", "Disyembre",
]
SOIL_NAMES_TL = {
    "Black Soil": "Itim na Lupa",
    "Red Soil": "Pulang Lupa",
    "Yellow Soil": "Dilaw na Lupa",
}


def ph_now():
    """Current date/time in Philippine Standard Time (UTC+8)."""
    return datetime.now(PH_TZ)


def _language(value):
    return "tl" if value == "tl" else "en"


def season_for(month, language="en"):
    """Return the Philippine season label for a month number (1-12)."""
    if _language(language) == "tl":
        if 6 <= month <= 11:
            return "Tag-ulan (Habagat)"
        if month in (12, 1, 2):
            return "Malamig at Tuyong Panahon (Amihan)"
        return "Mainit na Tag-araw (Summer)"

    if 6 <= month <= 11:
        return "Wet Season (Habagat)"
    if month in (12, 1, 2):
        return "Cool Dry Season (Amihan)"
    return "Hot Dry Season (Summer)"


def season_tip(month, language="en"):
    if _language(language) == "tl":
        if 6 <= month <= 11:
            return (
                "Tag-ulan ngayon — itaas ang bed, linisin ang drainage, at "
                "bantayan ang fungal disease. Pinakamaganda ngayon ang mga "
                "pananim na mahilig sa tubig at root crops."
            )
        if month in (12, 1, 2):
            return (
                "Ito ang pinakamagandang buwan para sa gulay — malamig at tuyo, "
                "perpekto para sa dahon-gulay at namumungang pananim tulad ng "
                "pechay, ampalaya, at talong."
            )
        return (
            "Ito ang pinakamainit na bahagi ng taon — mag-mulch nang makapal, "
            "magdilig nang malalim sa madaling umaga, at piliin ang mga pananim "
            "na matibay sa tagtuyot."
        )

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


def plant_now(soil=None, language="en", target_month=None, target_year=None):
    """Build the planting payload for a specific month (defaults to current month)."""
    now = ph_now()
    if target_month is not None and 1 <= int(target_month) <= 12:
        month = int(target_month)
        year = int(target_year) if target_year else now.year
    else:
        month = now.month
        year = now.year

    lang = _language(language)
    month_names = MONTH_NAMES_TL if lang == "tl" else MONTH_NAMES

    canonical_soil = canonical_name(soil) or soil
    crops = crops_for_month(month, canonical_soil)
    filtered_by_soil = bool(canonical_soil)
    note = None

    soil_name = display_name_for(canonical_soil) if canonical_soil else None
    if lang == "tl" and canonical_soil:
        soil_name = SOIL_NAMES_TL.get(canonical_soil, soil_name)

    if not crops and canonical_soil:
        crops = crops_for_month(month, None)
        filtered_by_soil = False
        if lang == "tl":
            note = (
                f"Walang pananim sa database na nakatugma sa {soil_name} para sa "
                f"{month_names[month - 1]}, kaya narito ang lahat ng pananim na "
                "bagay sa buwang ito."
            )
        else:
            note = (
                f"No crops in our database are mapped to {soil_name} for "
                f"{month_names[month - 1]}, so here are all crops suited to this month."
            )

    is_next = (
        (year == now.year and month == now.month + 1) or
        (now.month == 12 and month == 1 and year == now.year + 1)
    )

    return {
        "month": month,
        "month_name": month_names[month - 1],
        "year": year,
        "is_next_month": is_next,
        "season": season_for(month, lang),
        "season_tip": season_tip(month, lang),
        "soil_type": soil_name,
        "filtered_by_soil": filtered_by_soil,
        "crops": crops,
        "note": note,
        "count": len(crops),
        "language": lang,
    }

def _crop_line(crop, language="en"):
    days = ""
    if crop.get("harvest_days_min") and crop.get("harvest_days_max"):
        if _language(language) == "tl":
            days = f" — anihin sa {crop['harvest_days_min']}\u2013{crop['harvest_days_max']} araw"
        else:
            days = f" — harvest in {crop['harvest_days_min']}\u2013{crop['harvest_days_max']} days"
    local = f" ({crop['local_name']})" if crop.get("local_name") else ""
    return f"- **{crop['common_name']}**{local}{days}"


def format_planting_reply(result, language=None):
    """Render a plant_now() result as a chat-friendly markdown message."""
    lang = _language(language or result.get("language", "en"))
    month_name = result["month_name"]
    season = result["season"]
    year = result["year"]
    is_next = result.get("is_next_month", False)

    time_tag = f"**{month_name} {year}**"
    if is_next:
        time_tag += " _(Next Month)_" if lang != "tl" else " _(Susunod na Buwan)_"

    if not result["crops"]:
        if lang == "tl":
            return (
                f"Wala pa akong nakalista na pananim para sa {time_tag} ({season}).\n\n"
                "Subukang magtanong ng ibang buwan o mag-upload ng larawan ng lupa."
            )
        return (
            f"I don't have crops listed for {time_tag} ({season}) yet.\n\n"
            "Try asking about another month or upload a soil photo."
        )

    if lang == "tl":
        lines = [
            f"Narito ang puwede mong itanim para sa {time_tag} — "
            f"{season} sa Pilipinas:\n"
        ]
        if result["soil_type"] and result["filtered_by_soil"]:
            lines.append(f"Nasala para sa iyong **{result['soil_type']}**:\n")
        lines.extend(_crop_line(crop, lang) for crop in result["crops"])
        if result.get("note"):
            lines.append(f"\n_{result['note']}_")
        lines.append(f"\n**Tip para sa season:** {result['season_tip']}")
        return "\n".join(lines)

    lines = [
        f"Here's what you can plant for {time_tag} — "
        f"{season} in the Philippines:\n"
    ]
    if result["soil_type"] and result["filtered_by_soil"]:
        lines.append(f"Filtered for your **{result['soil_type']}**:\n")

    lines.extend(_crop_line(crop, lang) for crop in result["crops"])

    if result.get("note"):
        lines.append(f"\n_{result['note']}_")

    lines.append(f"\n**Season tip:** {result['season_tip']}")
    return "\n".join(lines)