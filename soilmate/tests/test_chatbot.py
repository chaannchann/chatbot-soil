"""Regression tests for the local chatbot engine.

Run with:  .venv/Scripts/python.exe tests/test_chatbot.py
No pytest required.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot import ChatBot  # noqa: E402

bot = ChatBot()
failures = []


def expect_intent(message, expected, session_id=None, soil=None):
    result = bot.respond(message, session_id=session_id, known_soil=soil)
    if result["intent"] != expected:
        failures.append(f"{message!r}: got {result['intent']!r}, expected {expected!r}")


def expect_soil(message, expected):
    got = bot.detect_soil(message)
    if got != expected:
        failures.append(f"soil {message!r}: got {got!r}, expected {expected!r}")


def check(condition, label):
    if not condition:
        failures.append(label)


# --- intent routing -----------------------------------------------------------
CASES = [
    # The two examples straight from the handoff document.
    ("How much compost should I mix with this yellow soil?", "compost_amount"),
    ("Why are my ampalaya leaves turning yellow?", "ampalaya_care"),
    ("What organic fertilizer is best for sandy soil in the Philippines?", "fertilizer_organic"),
    # Core knowledge areas.
    ("What can I plant now?", "what_to_plant_now"),
    ("what can you do", "help"),
    ("what is soil ph", "soil_ph_basics"),
    ("how do I test ph", "soil_ph_testing"),
    ("my soil is too acidic how do i fix it", "soil_ph_adjust"),
    ("how to make compost at home", "compost_making"),
    ("how often should i water my plants", "watering"),
    ("white powder on my leaves", "disease"),
    ("pests are eating my leaves", "pests"),
    ("what grows in red soil", "soil_red"),
    ("when is the best time to plant vegetables", "planting_season"),
    ("how long until harvest", "harvest"),
    ("can i grow pechay in pots", "container_gardening"),
    ("my plants are waterlogged after the rain", "drainage"),
    ("what is crop rotation", "crop_rotation"),
    ("how do i protect my garden from a typhoon", "typhoon"),
    ("mabuhay", "greeting"),
    ("salamat", "thanks"),
    ("how do i germinate seeds", "germination"),
    ("how to grow kalabasa", "crop_specific_care"),
    ("tell me about lettuce", "crop_specific_care"),
    ("garlic growing", "crop_specific_care"),
    ("tips for malunggay", "crop_specific_care"),
    ("ph", "soil_ph_basics"),
    ("compost", "compost_making"),
    ("red soil", "soil_red"),
    ("yellow", "soil_yellow"),
    ("sandy", "soil_yellow"),
    ("yellow leaves", "yellow_leaves"),
    # Must refuse to guess.
    ("what is the capital of france", "fallback"),
    ("who won the basketball game", "fallback"),
    ("tell me a joke", "fallback"),
    ("how do i cook adobo", "fallback"),
    ("give me a recipe for pancit", "fallback"),
    ("how do i fix my motorcycle", "fallback"),
    ("what is the weather tomorrow", "fallback"),
]

for message, expected in CASES:
    expect_intent(message, expected)

# --- soil detection -----------------------------------------------------------
expect_soil("yellow soil", "Yellow Soil")
expect_soil("this yellow soil", "Yellow Soil")
expect_soil("sandy soil", "Yellow Soil")
expect_soil("black soil", "Black Soil")
expect_soil("red clay", "Red Soil")
expect_soil("Why are my ampalaya leaves turning yellow?", None)
expect_soil("black spots on leaves", None)

# --- conversation context -----------------------------------------------------
bot.respond("What is yellow soil?", session_id="ctx-1")
reply = bot.respond("How much compost should I mix with this?", session_id="ctx-1")
check(reply["intent"] == "compost_amount", "follow-up should resolve to compost_amount")
check(reply["soil_type"] == "Yellow Soil", "follow-up should remember Yellow Soil")
check("5\u20138 kg" in reply["reply"], "follow-up should return the sandy-soil answer")

reply = bot.respond("How much compost should I mix in?", session_id="ctx-2", known_soil="Red Soil")
check(reply["soil_type"] == "Red Soil", "image-derived soil should be used")
check("lime" in reply["reply"].lower(), "red-soil answer should mention lime")

# --- robustness ---------------------------------------------------------------
check(bot.respond("", session_id="ctx-3")["intent"] == "empty", "empty message handled")
check(isinstance(reply["suggestions"], list), "suggestions should be a list")

if failures:
    print(f"FAILED ({len(failures)}):")
    for failure in failures:
        print("  -", failure)
    sys.exit(1)

print(f"All chatbot tests passed ({len(CASES)} intent cases + soil/context checks).")
