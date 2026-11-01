"""Canonical soil/surface names shared by inference, seeding, and planting.

The trained model and ``classes.json`` use raw folder names such as
``Clay_soil`` or ``soil_with_algae``. The database stores human-readable names
such as ``Clay Soil``. This module is the one place that maps every variant
(raw class key, display label, legacy underscore name, alias) to the canonical
database name, so lookups never depend on casing or underscores.
"""

import json
import os
import re
import unicodedata

SOILS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "soils.json"
)


def normalize_name(value):
    """Lowercase a name and collapse underscores, slashes, and punctuation."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[_\-/()]+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _load_catalog(path=SOILS_PATH):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    soils = data.get("soils", [])
    by_class = {}
    aliases = {}

    for soil in soils:
        class_key = soil["class_key"]
        name = soil["name"]
        display = soil.get("display_name", name)

        by_class[class_key] = soil

        # Every spelling the app may receive resolves to the same profile.
        variants = [class_key, name, display, *soil.get("aliases", [])]
        for variant in variants:
            key = normalize_name(variant)
            if key:
                aliases.setdefault(key, soil)

    return soils, by_class, aliases


SOILS, _BY_CLASS, _ALIASES = _load_catalog()


def soil_profile(value):
    """Return the catalog entry for any known name variant, or None."""
    if not value:
        return None
    if value in _BY_CLASS:
        return _BY_CLASS[value]
    return _ALIASES.get(normalize_name(value))


def canonical_name(value):
    """Return the name stored in ``soil_types.name`` for a known variant."""
    profile = soil_profile(value)
    return profile["name"] if profile else None


def display_name_for(value):
    """Return the label shown in the UI for a known variant.

    Unknown names are humanized instead of returned raw, so a new model class
    still looks sensible until it is added to ``data/soils.json``.
    """
    profile = soil_profile(value)
    if profile:
        return profile.get("display_name", profile["name"])

    text = str(value or "").replace("_", " ").strip()
    return text.title() if text else ""


def class_keys():
    """Raw class keys from the catalog, matching ``classes.json`` entries."""
    return list(_BY_CLASS)
