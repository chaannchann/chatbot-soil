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

# Filipino and Taglish questions must route to the same intents.
FILIPINO_CASES = [
    ("kumusta", "greeting"),
    ("ano ang ph ng lupa", "soil_ph_basics"),
    ("paano ko susuriin ang ph ng lupa", "soil_ph_testing"),
    ("paano aayusin ang acidic na lupa", "soil_ph_adjust"),
    ("paano gumawa ng compost", "compost_making"),
    ("gaano karaming compost ang ihahalo ko sa lupa", "compost_amount"),
    ("ano ang pinakamagandang organic fertilizer", "fertilizer_organic"),
    ("bakit naninilaw ang dahon ng ampalaya ko", "ampalaya_care"),
    ("paano magtanim ng pechay", "crop_specific_care"),
    ("ano ang tumutubo sa pulang lupa", "soil_red"),
    ("paano mapapabuti ang drainage", "drainage"),
    ("gaano kadalas akong magdidilig", "watering"),
    ("ano ang mulch", "mulch"),
    ("paano ko kokontrolin ang peste", "pests"),
    ("may puting pulbos ang dahon", "disease"),
    ("kailan pinakamagandang magtanim ng gulay", "planting_season"),
    ("ano ang puwedeng itanim ngayong buwan", "what_to_plant_now"),
    ("gaano katagal bago sumibol ang buto", "germination"),
    ("gaano katagal bago anihin", "harvest"),
    ("paano magtanim sa paso", "container_gardening"),
    ("crop rotation", "crop_rotation"),
    ("ano ang mga uri ng lupa", "soil_types_overview"),
    ("paano protektahan ang halaman sa bagyo", "typhoon"),
    ("salamat", "thanks"),
    # Colloquial variants that were previously falling back or misrouting.
    ("paano magdilig", "watering"),
    ("kailan magdilig", "watering"),
    ("gaano kadalas magdilig", "watering"),
    ("paano ayusin ang drainage", "drainage"),
    ("ano ang abono", "fertilizer_organic"),
    ("paano mag-alaga ng halaman sa paso", "container_gardening"),
    ("paano i-rotate ang pananim", "crop_rotation"),
    ("paano taasan ang ph", "soil_ph_adjust"),
    ("paano babaan ang ph", "soil_ph_adjust"),
    ("kailan anihin ang kamatis", "harvest"),
    ("paano magpataba ng pechay", "fertilizer_application"),
    ("tulong", "help"),
    ("salamat sa tulong", "thanks"),
    ("magandang umaga", "greeting"),
]

for message, expected in FILIPINO_CASES:
    expect_intent(message, expected)

# --- soil detection -----------------------------------------------------------
expect_soil("yellow soil", "Yellow Soil")
expect_soil("this yellow soil", "Yellow Soil")
expect_soil("sandy soil", "Yellow Soil")
expect_soil("black soil", "Black Soil")
expect_soil("red clay", "Red Soil")
expect_soil("itim na lupa", "Black Soil")
expect_soil("pulang lupa", "Red Soil")
expect_soil("dilaw na lupa", "Yellow Soil")
expect_soil("buhanging lupa", "Yellow Soil")
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

# --- Filipino responses -------------------------------------------------------
reply = bot.respond("paano gumawa ng compost")
check(reply["language"] == "tl", "Filipino question should set language=tl")
check("Madali ang composting" in reply["reply"], "Filipino question should get the Filipino answer")
check(
    reply["suggestions"] and "Gaano karaming compost" in reply["suggestions"][0],
    "Filipino question should get Filipino follow-ups",
)

reply = bot.respond("how to make compost")
check(reply["language"] == "en", "English question should stay English")
check("Composting is easy" in reply["reply"], "English question should get the English answer")

reply = bot.respond("magandang umaga")
check(reply["language"] == "tl", "Filipino greeting should set language=tl")
check(reply["title"] == "Pagbati", "Filipino greeting should use the Filipino title")

reply = bot.respond("tulong")
check(reply["intent"] == "help", "bare 'tulong' should route to help")
check(reply["language"] == "tl", "bare 'tulong' should be detected as Filipino")

reply = bot.respond("compost", preferred_language="tl")
check(reply["language"] == "tl", "UI language preference should localize ambiguous queries")
check("Madali ang composting" in reply["reply"], "preferred_language=tl should return Filipino")

reply = bot.respond("ano ang capital ng france")
check(reply["intent"] == "fallback", "Filipino unknown question should fall back")
check("Hindi ko pa" in reply["reply"], "Filipino fallback should be in Filipino")

reply = bot.respond("what is the capital of france", preferred_language="tl")
check(reply["language"] == "tl", "preferred_language should localize the fallback")
check("Hindi ko pa" in reply["reply"], "preferred_language=tl fallback should be Filipino")

bot.respond("ano ang dilaw na lupa", session_id="ctx-tl")
reply = bot.respond("gaano karaming compost ang ihahalo ko dito", session_id="ctx-tl")
check(reply["intent"] == "compost_amount", "Filipino follow-up should resolve to compost_amount")
check(reply["soil_type"] == "Yellow Soil", "Filipino follow-up should remember Yellow Soil")
check("5\u20138 kg" in reply["reply"], "Filipino follow-up should return the sandy-soil answer")
check(reply["language"] == "tl", "Filipino follow-up should stay Filipino")

# --- robustness ---------------------------------------------------------------
check(bot.respond("", session_id="ctx-3")["intent"] == "empty", "empty message handled")
check(isinstance(reply["suggestions"], list), "suggestions should be a list")

if failures:
    print(f"FAILED ({len(failures)}):")
    for failure in failures:
        print("  -", failure)
    sys.exit(1)

print(
    f"All chatbot tests passed ({len(CASES) + len(FILIPINO_CASES)} intent cases "
    "+ soil/context/language checks)."
)
