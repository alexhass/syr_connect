"""Water hardness units of the SYR devices (getWHU) and their conversion.

Each device family numbers the units of getWHU differently. A signature names the table
of its family (`whu_units`); `SyrConnectModelSignature.whu_unit()` gives the unit of a
code and `hardness_factor()` the conversion for the devices that keep the water
hardness in °dH.
"""

from collections.abc import Mapping
import math

# Water hardness unit codes (getWHU) of the device families: code -> unit. Each family
# numbers the units differently, see docs/syrconnect-protocol.md.
WHU_UNITS_LEX: Mapping[int, str] = {
    0: "°dH",
    1: "°fH",
    2: "°e",
    3: "mg/l CaCO₃",
    4: "ppm",
    5: "mmol/l",
    6: "mval/l",
}
WHU_UNITS_MUCO: Mapping[int, str] = {
    0: "°dH",
    1: "°e",
    2: "°fH",
    3: "ppm",
}
WHU_UNITS_NEOSOFT: Mapping[int, str] = {
    0: "°dH",
    1: "mmol/l",
    2: "°fH",
}

# Water hardness units as multiples of 1 °dH, for devices that keep the water hardness
# in °dH and use getWHU only for the display (`hardness_in_dh` of the signature)
WHU_FACTORS_FROM_DH: Mapping[str, float] = {
    "°dH": 1.0,
    "°e": 1.25216338,
    "°fH": 1.78480457,
    "ppm": 17.8480457,
}


def round_hardness(value: float) -> int:
    """Round a converted water hardness to a whole number, halves up."""
    return math.floor(value + 0.5)
