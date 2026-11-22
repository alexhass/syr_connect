"""Commands of the SYR devices: the set command of a key and the value it takes.

A setting is written with the set command of its status key (getRMN -> setRMN). Many
commands take their value in the format the device reports for the key, or a value that
depends on the device (setSIR, setDEX). Some commands have no status key of their own;
another key tells that the device has the function (`COMMAND_STATUS_KEYS`). The commands
are sent with `set_device_status()` of the client.
"""

from collections.abc import Mapping
import logging
from typing import Any

from .models import SyrConnectModelSignature, SyrConnectStatus, SyrConnectStatusValue
from .values import is_value_true

_LOGGER = logging.getLogger(__name__)

# Commands without a status key of their own: command -> status key that tells the device
# has the function. The microleakage test (setDEX) shows its state in getDSV. A hygiene
# module reports no getMFC/getMFW; the stagnation time of the line (getSCF, getSWF) shows
# that the line exists.
COMMAND_STATUS_KEYS: Mapping[str, str] = {
    "setDEX": "getDSV",
    "setMFC": "getSCF",
    "setMFW": "getSWF",
}

# Commands that only the local JSON API takes
JSON_ONLY_COMMANDS: frozenset[str] = frozenset(
    {
        "setDEX",
    }
)

# Commands that take no value: the manual flushing of a hygiene module line (setMFC,
# setMFW) and the firmware update (setUPG)
TRIGGER_COMMANDS: frozenset[str] = frozenset(
    {
        "setMFC",
        "setMFW",
        "setUPG",
    }
)


def set_command(key: str) -> str:
    """Return the command that writes a status key ("getRMN" -> "setRMN").

    Args:
        key: Status key, e.g. "getRMN"

    Returns:
        The set command of the key
    """
    return f"set{key[3:]}"


def command_status_key(signature: SyrConnectModelSignature, command: str) -> str:
    """Return the status key that tells the device has the function of a command.

    Formats:
    - Alarm reset: "setALA" -> "getALM" or "getALA" (`alarm_status_key`)
    - Command of `COMMAND_STATUS_KEYS`: "setDEX" -> "getDSV"
    - Other commands: "setNOT" -> "getNOT"

    Args:
        signature: Signature of the model
        command: The command, e.g. "setNOT"

    Returns:
        The status key, which also holds the code a reset command resets
    """
    if command == "setALA":
        return signature.alarm_status_key
    return COMMAND_STATUS_KEYS.get(command, f"get{command[3:]}")


def build_trigger_command(command: str) -> tuple[str, str]:
    """Return a command of `TRIGGER_COMMANDS` with its empty value.

    Args:
        command: The command, e.g. "setMFC"

    Returns:
        (command, "")
    """
    return command, ""


def build_reset_command(
    signature: SyrConnectModelSignature, command: str, clear_value: str | int
) -> tuple[str, str | int]:
    """Return the command that resets an alarm, a notification or a warning.

    Formats:
    - Alarm (setALA): the command of `alarm_reset_command()` of the model
    - Notification or warning (setNOT, setWRN): the command with the clear value

    Args:
        signature: Signature of the model
        command: "setALA", "setNOT" or "setWRN"
        clear_value: The value of the client that acknowledges a code ("FF" in the
            cloud, 255 on the device)

    Returns:
        The (command, value) pair to send
    """
    if command == "setALA":
        return signature.alarm_reset_command(clear_value)
    return command, clear_value


def build_sir_command(status: SyrConnectStatus) -> tuple[str, int | str]:
    """Return the command that starts a manual regeneration (setSIR).

    The value follows the format of getSIR:
    - getSIR False or "false": "true"
    - Any other getSIR (e.g. "1", 1): 0

    Args:
        status: Status of the device

    Returns:
        ("setSIR", value)
    """
    raw_sir = status.get("getSIR")
    if raw_sir is False or str(raw_sir).strip().lower() == "false":
        return "setSIR", "true"
    return "setSIR", 0


def is_microleakage_test_running(status: SyrConnectStatus) -> bool:
    """Return True if a microleakage test is running (getDSV 1)."""
    return str(status.get("getDSV")).strip() == "1"


def build_dex_command(status: SyrConnectStatus) -> tuple[str, int | str]:
    """Return the command that starts the microleakage test (setDEX).

    The value depends on the device type (getTYP):
    - getTYP below 100: 1
    - getTYP 100 or more, absent or not numeric: "true"

    Args:
        status: Status of the device

    Returns:
        ("setDEX", value)
    """
    typ: Any = status.get("getTYP")
    try:
        return "setDEX", 1 if int(typ) < 100 else "true"
    except ValueError, TypeError:
        return "setDEX", "true"


def is_flag_enabled(
    signature: SyrConnectModelSignature, key: str, value: SyrConnectStatusValue
) -> bool:
    """Return True if a flag reports its function as enabled.

    A flag of `inverted_flags` reports the opposite, e.g. True for "disabled".

    Args:
        signature: Signature of the model
        key: Status key of the flag, e.g. "getFD1"
        value: Reported value of the flag

    Returns:
        True if the function is enabled; an unknown value counts as False before the
        inversion
    """
    enabled = is_value_true(value)
    return not enabled if key in signature.inverted_flags else enabled


def build_flag_command(
    signature: SyrConnectModelSignature,
    status: SyrConnectStatus,
    key: str,
    enabled: bool,
) -> tuple[str, bool | int | str]:
    """Return the command that enables or disables the function of a flag.

    The value is inverted for a flag of `inverted_flags` and follows the format of the
    reported value:
    - bool: True / False
    - int: 1 / 0
    - "0" or "1": "1" / "0"
    - Anything else: "True" / "False"

    Args:
        signature: Signature of the model
        status: Status of the device
        key: Status key of the flag, e.g. "getBUZ"
        enabled: True to enable the function

    Returns:
        The (command, value) pair to send
    """
    state = not enabled if key in signature.inverted_flags else enabled
    current = status.get(key)
    value: bool | int | str
    if isinstance(current, bool):
        value = state
    elif isinstance(current, int):
        value = 1 if state else 0
    elif isinstance(current, str) and current.strip() in ("0", "1"):
        value = "1" if state else "0"
    else:
        value = "True" if state else "False"
    return set_command(key), value


def build_cartridge_type_commands(
    signature: SyrConnectModelSignature,
    status: SyrConnectStatus,
    cartridge_type: int | None,
) -> list[tuple[str, Any]]:
    """Return the commands that select the cartridge type (getCRT) of the water treatment.

    The water treatment (getWTR) and the cartridge type are one setting: no cartridge
    switches the water treatment off, a cartridge type is set together with switching
    the water treatment on. setWTR takes the format of the reported getWTR
    (`build_flag_command()`).

    Formats:
    - No cartridge, getWTR reported: [("setWTR", "0")]
    - No cartridge, no getWTR: [] (cannot be selected)
    - Type 1, water treatment on: [("setCRT", 1)]
    - Type 1, water treatment off: [("setCRT", 1), ("setWTR", "1")]

    Args:
        signature: Signature of the model
        status: Status of the device
        cartridge_type: Raw cartridge type (0=HWE, 1=HVE, 2=HVE+), None for no cartridge

    Returns:
        The (command, value) pairs to send together, empty if the selection cannot be
        written
    """
    has_water_treatment = bool(signature.cartridge_keys) and status.get(
        "getWTR"
    ) not in (None, "")
    if cartridge_type is None:
        if not has_water_treatment:
            return []
        return [build_flag_command(signature, status, "getWTR", False)]
    commands: list[tuple[str, Any]] = [(set_command("getCRT"), cartridge_type)]
    if signature.is_water_treatment_off(status):
        commands.append(build_flag_command(signature, status, "getWTR", True))
    return commands


def filling_refusal(
    signature: SyrConnectModelSignature, status: SyrConnectStatus, key: str
) -> str | None:
    """Return why the device refuses to start a filling now, or None if it starts it.

    The initial (getIFL) and the manual filling (getMFL) can only be started while the
    automatic filling mode (getDFI) is off, the initial filling also only while the
    device is idle (getSTA 0). Stopping a filling is always allowed.

    Args:
        signature: Signature of the model
        status: Status of the device
        key: "getIFL" or "getMFL"

    Returns:
        "filling_mode" while the automatic filling mode is on, "not_standby" while the
        device is not idle (initial filling only), otherwise None
    """
    dfi = status.get("getDFI")
    if dfi is not None and is_flag_enabled(signature, "getDFI", dfi):
        _LOGGER.debug("Filling %s refused: automatic filling mode is on", key)
        return "filling_mode"
    sta = status.get("getSTA")
    if key == "getIFL" and sta is not None and str(sta) != "0":
        _LOGGER.debug("Filling %s refused: device is not idle (getSTA=%s)", key, sta)
        return "not_standby"
    return None
