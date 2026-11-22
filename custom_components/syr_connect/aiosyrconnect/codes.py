"""Alarm, notification and warning codes of the SYR devices (getALA, getALM, getNOT, getWRN).

The devices report "no code" in several ways, see "Resetting alarms, notifications and
warnings" in docs/syrconnect-protocol.md. `is_code_active()` tells an active code from
these values.
"""

# Values that mean "no code", compared after strip().upper(). The device reports "FF"
# after a reset; 255 is the decimal reset value of the JSON API (`clear_value`).
NO_CODE_VALUES: frozenset[str] = frozenset({"", "0", "00", "FF", "A0X0000", "255"})


def is_code_active(value: object) -> bool:
    """Return True if an alarm, notification or warning code is active.

    Args:
        value: Value of getALA, getALM, getNOT or getWRN, None if the device does not
            report it

    Returns:
        False for None and the values of `NO_CODE_VALUES`, True otherwise
    """
    return value is not None and str(value).strip().upper() not in NO_CODE_VALUES
