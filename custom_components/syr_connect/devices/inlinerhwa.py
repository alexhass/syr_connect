"""Device profile for the Inliner-HWA 3300 (dk=25).

Provisional: no fixture of this device exists yet. Sensors and binary sensors keep
the global allowlists; settings (selects, switches, buttons, valves) stay disabled
until a capture of a real device shows its keys. The device reports the alarm codes
of the Safe-T family (devices/safetplus.py).
"""

from . import SyrConnectDeviceProfile
from .safetplus import ALA_CODES

SELECT_SUPPORTED_KEYS: set[str] = set()

SWITCH_SUPPORTED_KEYS: set[str] = set()

BUTTON_SUPPORTED_KEYS: set[str] = set()

VALVE_SUPPORTED_KEYS: set[str] = set()


PROFILE = SyrConnectDeviceProfile(
    ala_codes=ALA_CODES,
    binary_sensor=None,
    button=BUTTON_SUPPORTED_KEYS,
    select=SELECT_SUPPORTED_KEYS,
    sensor=None,
    switch=SWITCH_SUPPORTED_KEYS,
    valve=VALVE_SUPPORTED_KEYS,
)
