"""Regression tests for soil name normalization.

Run with:  python tests/test_soil_catalog.py
No pytest or database required.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soil_catalog import (  # noqa: E402
    SOILS,
    canonical_name,
    display_name_for,
    normalize_name,
)

failures = []


def check(condition, label):
    if not condition:
        failures.append(label)


EXPECTED = {
    "Alluvial_soil": ("Alluvial Soil", "Alluvial Soil"),
    "Black_Soil": ("Black Soil", "Black Soil"),
    "Cinder_Soil": ("Cinder Soil", "Cinder Soil"),
    "Clay_soil": ("Clay Soil", "Clay Soil"),
    "Laterite_Soil": ("Laterite Soil", "Laterite Soil"),
    "Peat_Soil": ("Peat Soil", "Peat Soil"),
    "Red_soil": ("Red Soil", "Red Soil"),
    "Yellow_Soil": ("Yellow Soil", "Yellow / Sandy Soil"),
    "concrete_surface": ("Concrete Surface", "Concrete Surface (Non-Soil)"),
    "soil_with_algae": ("Soil with Algae", "Soil with Algae / Biocrust"),
}

for class_key, (name, display) in EXPECTED.items():
    check(canonical_name(class_key) == name, f"{class_key}: canonical name")
    check(display_name_for(class_key) == display, f"{class_key}: display name")

# Every class emitted by the model must have a catalog profile.
with open(os.path.join(ROOT, "classes.json"), encoding="utf-8") as fh:
    class_names = json.load(fh)

for class_key in class_names:
    check(canonical_name(class_key) is not None, f"{class_key}: missing from soils.json")

# Display labels stored in scan history must resolve back to the same profile.
for class_key, (name, display) in EXPECTED.items():
    check(canonical_name(display) == name, f"{display}: round-trip canonical name")

# Legacy database names and casual spellings.
check(canonical_name("concrete_surface") == "Concrete Surface", "legacy concrete")
check(canonical_name("Concrete Surface (Non-Soil)") == "Concrete Surface", "concrete display")
check(canonical_name("soil_with_algae") == "Soil with Algae", "legacy algae")
check(canonical_name("Soil with Algae / Biocrust") == "Soil with Algae", "algae display")
check(canonical_name("Yellow / Sandy Soil") == "Yellow Soil", "yellow display")
check(canonical_name("Clay_soil") == "Clay Soil", "raw clay")
check(canonical_name("  cLaY   sOiL  ") == "Clay Soil", "case and whitespace")
check(canonical_name("sandy soil") == "Yellow Soil", "sandy alias")
check(normalize_name("Soil-with_Algae/Biocrust") == "soil with algae biocrust", "normalizer")
check(canonical_name("unobtainium") is None, "unknown name should not resolve")

# Every profile should have usable card copy.
for soil in SOILS:
    label = soil["name"]
    check(bool(soil.get("description")), f"{label}: description")
    check(bool(soil.get("improvement_tips")), f"{label}: improvement tips")
    check(bool(soil.get("class_key")), f"{label}: class_key")

if failures:
    print(f"FAILED ({len(failures)}):")
    for failure in failures:
        print("  -", failure)
    sys.exit(1)

print(f"All soil catalog tests passed ({len(SOILS)} profiles, {len(class_names)} model classes).")
