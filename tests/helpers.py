"""
tests/helpers.py
----------------
Synthetic 21-point MediaPipe hand builder.

Lets the classifier be tested without a camera. Coordinates are normalised
(y grows downwards, exactly like MediaPipe), and each finger is placed so
that it is genuinely extended or genuinely folded rather than borderline.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LM:
    x: float
    y: float
    z: float = 0.0


# thumb poses: tucked (folded), lateral (spread wide), up / down (thumbs),
# rest (relaxed), shaka (thumb spread + pinky up)
THUMB_POSES = ("tucked", "lateral", "up", "down", "rest", "shaka")


def make_hand(
    fingers=(False, False, False, False),
    thumb="tucked",
    jitter=0.0,
) -> list[LM]:
    """
    Build a synthetic right-ish hand.

    Parameters
    ----------
    fingers : (index, middle, ring, pinky) — True means extended
    thumb   : one of THUMB_POSES
    jitter  : optional coordinate noise, to simulate detection wobble
    """
    lm: list[LM | None] = [None] * 21

    lm[0] = LM(0.50, 0.900)          # wrist
    lm[1] = LM(0.450, 0.780)         # thumb CMC
    lm[2] = LM(0.405, 0.705)         # thumb MCP

    rows = [
        # index
        dict(mcp=LM(0.420, 0.600),
             up=[LM(0.415, 0.470), LM(0.410, 0.400), LM(0.405, 0.330)],
             dn=[LM(0.415, 0.500), LM(0.405, 0.570), LM(0.415, 0.650)]),
        # middle
        dict(mcp=LM(0.500, 0.580),
             up=[LM(0.500, 0.440), LM(0.500, 0.365), LM(0.500, 0.290)],
             dn=[LM(0.500, 0.480), LM(0.492, 0.550), LM(0.500, 0.630)]),
        # ring
        dict(mcp=LM(0.580, 0.600),
             up=[LM(0.585, 0.470), LM(0.590, 0.400), LM(0.595, 0.335)],
             dn=[LM(0.585, 0.500), LM(0.594, 0.570), LM(0.585, 0.650)]),
        # pinky
        dict(mcp=LM(0.655, 0.640),
             up=[LM(0.655, 0.545), LM(0.660, 0.485), LM(0.665, 0.430)],
             dn=[LM(0.652, 0.560), LM(0.648, 0.610), LM(0.652, 0.690)]),
    ]

    for f, row in enumerate(rows):
        base = 5 + f * 4
        lm[base] = row["mcp"]
        seg = row["up"] if fingers[f] else row["dn"]
        lm[base + 1], lm[base + 2], lm[base + 3] = seg

    # ── thumb ────────────────────────────────────────────────────────────
    if thumb == "lateral":
        # spread wide: far from palm centre
        lm[3] = LM(0.350, 0.645)
        lm[4] = LM(0.300, 0.600)
    elif thumb == "up":
        # straight and clearly above the index knuckle
        lm[2] = LM(0.440, 0.720)
        lm[3] = LM(0.435, 0.640)
        lm[4] = LM(0.435, 0.545)
    elif thumb == "down":
        # straight and clearly below the index knuckle
        lm[2] = LM(0.440, 0.700)
        lm[3] = LM(0.430, 0.780)
        lm[4] = LM(0.425, 0.870)
    elif thumb == "shaka":
        # spread, thumb pointing up-and-out (call me)
        lm[3] = LM(0.360, 0.660)
        lm[4] = LM(0.330, 0.600)
    elif thumb == "rest":
        # relaxed across the palm — folded, neither clearly up nor down
        lm[3] = LM(0.420, 0.690)
        lm[4] = LM(0.455, 0.645)
    else:  # tucked
        lm[3] = LM(0.420, 0.665)
        lm[4] = LM(0.470, 0.630)

    out = [p if p is not None else LM(0.5, 0.5) for p in lm]

    if jitter:
        import math
        out = [
            LM(
                p.x + math.sin(i * 12.9898) * jitter,
                p.y + math.sin(i * 5.233 + 1.7) * jitter * 0.7,
                p.z,
            )
            for i, p in enumerate(out)
        ]
    return out


# ── Convenience builders, one per gesture ────────────────────────────────────
def palm()        -> list[LM]: return make_hand((1, 1, 1, 1), "lateral")
def palm_hi()     -> list[LM]: return make_hand((1, 1, 1, 1), "up")
def four()        -> list[LM]: return make_hand((1, 1, 1, 1), "tucked")
def three()       -> list[LM]: return make_hand((1, 1, 1, 0), "tucked")
def three_thumb() -> list[LM]: return make_hand((1, 1, 1, 0), "lateral")
def peace()       -> list[LM]: return make_hand((1, 1, 0, 0), "tucked")
def point()       -> list[LM]: return make_hand((1, 0, 0, 0), "tucked")
def point_thumb() -> list[LM]: return make_hand((1, 0, 0, 0), "lateral")
def horns()       -> list[LM]: return make_hand((1, 0, 0, 1), "tucked")
def call_me()     -> list[LM]: return make_hand((0, 0, 0, 1), "shaka")
def thumbs_up()   -> list[LM]: return make_hand((0, 0, 0, 0), "up")
def thumbs_down() -> list[LM]: return make_hand((0, 0, 0, 0), "down")
def fist()        -> list[LM]: return make_hand((0, 0, 0, 0), "tucked")
def fist_rest()   -> list[LM]: return make_hand((0, 0, 0, 0), "rest")
def ambiguous()   -> list[LM]: return make_hand((1, 0, 1, 0), "tucked")
