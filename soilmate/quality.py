"""Image sanity checks for soil photos.

A softmax classifier always returns one of its trained classes, so a photo of
grass or a wall can still score high. These cheap, fully local heuristics catch
obviously unusable photos first and let the API return a specific, actionable
message instead of a confident-but-wrong prediction.

Heuristics only: no retraining and no extra model.
"""

import math

from PIL import Image, ImageStat

MIN_DIMENSION = 120

# Mean brightness floor. Set low on purpose: a real photo of a dark, freshly
# tilled field measures around 31/255, so only near-black images are rejected.
MIN_BRIGHTNESS = 20
MAX_BRIGHTNESS = 232
MIN_CONTRAST = 10

# Fraction of pixels that must look like earth (brown/orange/red/yellow) or
# neutral grey/brown before we accept the photo as soil at all. A photo of a
# building and sky scored 0.20; genuine soil photos scored 0.39-1.00.
MIN_EARTH_FRACTION = 0.30

TIPS = [
    "Fill the frame with soil - avoid including sky, plants, or tools.",
    "Shoot in soft daylight; avoid harsh shadows and direct flash glare.",
    "Get close enough that the soil texture is visible, and hold steady.",
]


def message_for(reason, **context):
    if reason == "too_small":
        return (
            f"That image is too small to analyse reliably "
            f"({context['width']}x{context['height']} pixels). "
            "Please upload a larger photo - at least 300x300 pixels."
        )
    if reason == "too_dark":
        return (
            "That photo is too dark for me to read the soil. "
            "Move into natural daylight or use your phone's torch, then try again."
        )
    if reason == "too_bright":
        return (
            "That photo is washed out - it looks overexposed. "
            "Avoid direct glare or shooting straight into the sun, and try again."
        )
    if reason == "flat":
        return (
            "That image looks flat or blurry, with almost no visible texture. "
            "Move closer to the soil surface and make sure it is in focus."
        )
    if reason == "not_soil":
        return (
            "That doesn't look like soil - it seems to be mostly plants, sky, "
            "or another surface. Point the camera directly at the soil itself "
            "so it fills most of the frame."
        )
    if reason == "low_confidence":
        return (
            "I could not clearly identify this soil type. The photo might be "
            "blurry, poorly lit, or a soil type I wasn't trained on. "
            "Please provide a clear, close-up photo of the soil surface."
        )
    return "I could not analyse that image."


def _earth_fraction(image):
    """Share of pixels whose colour plausibly belongs to soil."""
    sample = image.convert("RGB").resize((96, 96))
    hue, sat, val = sample.convert("HSV").split()
    hues = list(hue.getdata())
    sats = list(sat.getdata())
    vals = list(val.getdata())

    earth = 0
    for h, s, v in zip(hues, sats, vals):
        # Ignore blown-out highlights and crushed black shadows.
        if v < 20 or v > 245:
            continue
        # Brown / orange / red / yellow hues, or low-saturation neutrals.
        if s < 45 or h <= 55 or h >= 220:
            earth += 1

    return earth / len(hues)


def assess_image(image):
    """Return {'ok': bool, 'reason': str|None, 'message': str, 'tips': list}."""
    width, height = image.size
    if min(width, height) < MIN_DIMENSION:
        return {
            "ok": False,
            "reason": "too_small",
            "message": message_for("too_small", width=width, height=height),
            "tips": ["Upload at least 300x300 pixels for a reliable reading."],
        }

    rgb = image.convert("RGB").resize((96, 96))
    stats = ImageStat.Stat(rgb.convert("L"))
    mean_brightness = stats.mean[0]
    contrast = stats.stddev[0]

    if mean_brightness < MIN_BRIGHTNESS:
        return {"ok": False, "reason": "too_dark",
                "message": message_for("too_dark"), "tips": TIPS}

    if mean_brightness > MAX_BRIGHTNESS:
        return {"ok": False, "reason": "too_bright",
                "message": message_for("too_bright"), "tips": TIPS}

    if contrast < MIN_CONTRAST:
        return {"ok": False, "reason": "flat",
                "message": message_for("flat"), "tips": TIPS}

    earth = _earth_fraction(rgb)
    if earth < MIN_EARTH_FRACTION:
        return {"ok": False, "reason": "not_soil",
                "message": message_for("not_soil"), "tips": TIPS}

    return {"ok": True, "reason": None, "message": "", "tips": []}


def normalised_entropy(probabilities):
    """Softmax entropy scaled to 0-1 (1 = completely undecided)."""
    values = [float(p) for p in probabilities if p > 0]
    if len(values) <= 1:
        return 0.0
    entropy = -sum(p * math.log(p) for p in values)
    return entropy / math.log(len(probabilities))
