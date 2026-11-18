"""Tests for the device profile helpers (helpers/profile.py)."""

from dataclasses import replace
import importlib
import pkgutil
from typing import Any

import pytest

from custom_components.syr_connect import devices
from custom_components.syr_connect.aiosyrconnect import SyrConnectStatus
from custom_components.syr_connect.devices import (
    hva,
    lex,
    muco_connectioncentre,
    muco_filling,
    muco_leakprotect,
    safefloor,
    safetech,
    safetechplus,
    safetplus,
    trio,
)
from custom_components.syr_connect.helpers.profile import (
    get_cartridge_entity_keys,
    get_cartridge_keys,
    get_hardness_factor,
    get_hardness_range,
    get_model_supported_keys,
    get_sensor_ala_map,
    get_sensor_not_map,
    get_sensor_wrn_map,
    round_hardness,
)
from custom_components.syr_connect.models import (
    MODEL_SIGNATURES,
    UNKNOWN_MODEL,
    SyrConnectModel,
    detect_model,
)
from custom_components.syr_connect.sensor import is_sensor_visible

# The profiles of all device files, keyed by module name.
_DEVICE_PROFILES = {
    module.name: importlib.import_module(f"{devices.__name__}.{module.name}").PROFILE
    for module in pkgutil.iter_modules(devices.__path__)
}


def _signature(name: str) -> SyrConnectModel:
    """Return the model signature with the given name."""
    return next(signature for signature in MODEL_SIGNATURES if signature.name == name)


def test_get_sensor_maps_and_visibility_additional() -> None:
    """Test get sensor maps and visibility additional."""
    # NOT/WRN mapping with the common codes
    model = _signature("neosoft2500")
    assert get_sensor_not_map(model, "01")[0] == "new_software_available"
    assert get_sensor_wrn_map(model, "01")[0] == "power_outage"
    assert get_sensor_not_map(UNKNOWN_MODEL, "01") == (None, "01")
    assert get_sensor_wrn_map(UNKNOWN_MODEL, "01") == (None, "01")

    # ALA mapping with detected model
    status: SyrConnectStatus = {"getCNA": "LEXplus10"}
    assert get_sensor_ala_map(detect_model(status), "0")[0] == "no_alarm"

    # Unknown model has no alarm codes: the raw code is kept
    assert get_sensor_ala_map(UNKNOWN_MODEL, "A5") == (None, "A5")

    # Visibility rules
    status = {"getPA1": "true", "getPV1": "5"}
    assert is_sensor_visible(status, "getPV1", "1") is True
    # getRTIME is not in the allowlist, so it is never passed to is_sensor_visible;
    # the function only applies visibility rules, not exclusions.
    assert is_sensor_visible({}, "getRTIME", "x") is True


def test_sensor_code_mappings_and_unknown_model() -> None:
    """Test ALA/NOT/WRN mapping functions and unknown-model behavior."""

    # ALA: LEX family (detect via getCNA)
    status_lex = {"getCNA": "LEXplus10S"}
    mapped, raw = get_sensor_ala_map(detect_model(status_lex), "0")
    assert mapped == "no_alarm" and raw == "0"

    # ALA: NeoSoft family (detect via serial number prefix)
    status_neo = {"getSRN": "200AAA12345", "getVER": "NSS.V.2.028"}
    mapped2, raw2 = get_sensor_ala_map(detect_model(status_neo), "FF")
    assert mapped2 == "no_alarm" and raw2 == "FF"

    # ALA: Safe-T+ family (detect via getVER prefix)
    status_safet = {"getVER": "Safe-T+ V2.00e"}
    mapped3, raw3 = get_sensor_ala_map(detect_model(status_safet), "A1")
    assert mapped3 == "alarm_safet_valve_cannot_be_operated" and raw3 == "A1"

    # ALA: unknown model -> no mapping
    mapped4, raw4 = get_sensor_ala_map(UNKNOWN_MODEL, "A5")
    assert mapped4 is None and raw4 == "A5"

    # NOT mapping
    model = _signature("triols")
    mapped_not, raw_not = get_sensor_not_map(model, "01")
    assert mapped_not == "new_software_available" and raw_not == "01"
    mapped_not2, raw_not2 = get_sensor_not_map(model, "")
    assert mapped_not2 == "no_notification" and raw_not2 == ""

    # WRN mapping
    mapped_wrn, raw_wrn = get_sensor_wrn_map(model, "02")
    assert mapped_wrn == "salt_supply_low" and raw_wrn == "02"
    mapped_wrn2, raw_wrn2 = get_sensor_wrn_map(UNKNOWN_MODEL, None)
    assert mapped_wrn2 is None and raw_wrn2 == ""


def test_mapping_none_inputs() -> None:
    """Ensure mapping functions handle None/empty raw codes."""
    mapped_ala, raw_ala = get_sensor_ala_map(UNKNOWN_MODEL, None)
    assert mapped_ala is None and raw_ala == ""

    mapped_not, raw_not = get_sensor_not_map(UNKNOWN_MODEL, None)
    assert mapped_not is None and raw_not == ""


def test_get_sensor_ala_map_known_model_unmapped_codes() -> None:
    """Known models but with unmapped raw codes should return (None, raw)."""
    model = _signature("lexplus10")
    mapped, raw = get_sensor_ala_map(model, "ZZ")
    assert mapped is None and raw == "ZZ"

    model = _signature("safetplus")
    mapped, raw = get_sensor_ala_map(model, "ZZ")
    assert mapped is None and raw == "ZZ"

    model = _signature("neosoft2500")
    mapped, raw = get_sensor_ala_map(model, "ZZ")
    assert mapped is None and raw == "ZZ"

    model = _signature("safefloor")
    mapped, raw = get_sensor_ala_map(model, "ZZ")
    assert mapped is None and raw == "ZZ"


def test_get_sensor_ala_map_normalizes_case_of_raw_value() -> None:
    """Raw API values are uppercased before lookup, so mixed-case codes like LowBat match."""
    model = _signature("safetplus")
    assert get_sensor_ala_map(model, "LowBat") == ("alarm_battery_low", "LowBat")
    assert get_sensor_ala_map(model, "weakbat") == ("alarm_battery_weak", "weakbat")

    model = _signature("neosoft2500")
    assert get_sensor_ala_map(model, "a1")[0] == "alarm_end_switch"


def test_get_sensor_ala_map_covers_all_signatures_of_known_families() -> None:
    """Every signature using a MuCo/NeoSoft/SafeTech/Trio/LEX/Safe-T+ device file gets a mapping."""

    families = ("muco_", "neosoft_", "safetech", "trio", "lex", "safetplus")
    checked = 0
    for signature in MODEL_SIGNATURES:
        device_file = next(
            (
                name
                for name, profile in _DEVICE_PROFILES.items()
                if profile is signature.device_profile
            ),
            "",
        )
        if not device_file.startswith(families):
            continue
        code = "0" if device_file.startswith("lex") else "FF"
        mapped, _raw = get_sensor_ala_map(signature, code)
        assert mapped == "no_alarm", signature.name
        checked += 1
    assert checked > 40


@pytest.mark.parametrize(
    ("name", "code", "expected"),
    [
        ("neosoft2500", "11", "regeneration_required"),
        ("neosoft2500", "1A", "system_time_lost"),
        ("syrac3228connect", "09", "initial_filling"),
        ("safetechplus", "A6", "microleakage_suspected"),
        ("safetech", "FF", "no_warning"),
        ("safetech", "01", None),
        ("safetechpluswifi", "01", None),
        ("hva", "ff", "no_warning"),
    ],
)
def test_get_sensor_wrn_map_family_codes(
    name: str, code: str, expected: str | None
) -> None:
    """The warning codes follow the table of the device family."""
    assert get_sensor_wrn_map(_signature(name), code) == (expected, code)


@pytest.mark.parametrize(
    ("name", "code", "expected"),
    [
        ("optimabackwash", "09", "backwash_reminder_pressure"),
        ("lex10", "FF", "no_notification"),
        ("lex10", "01", None),
        ("safetech", "04", None),
        ("controlicmini", "FF", None),
    ],
)
def test_get_sensor_not_map_family_codes(
    name: str, code: str, expected: str | None
) -> None:
    """The notification codes follow the table of the device family."""
    assert get_sensor_not_map(_signature(name), code) == (expected, code)


def test_get_sensor_ala_map_every_device_profile_has_alarm_codes() -> None:
    """Every device file names the alarm codes of its family."""
    for name, profile in _DEVICE_PROFILES.items():
        assert profile.ala_codes is not None, name


@pytest.mark.parametrize(
    ("name", "code", "expected"),
    [
        ("neosoft2500", "AC", "alarm_increased_water_hardness"),
        ("neosoft2500", "AD", "alarm_conductivity_sensor_2_faulty"),
        ("neosoft2500", "AE", "alarm_valve_no_movement"),
        ("neosoft2500", "AF", "alarm_pressure_sensor_2_faulty"),
        ("neosoft2500", "01", "alarm_pressure_too_low"),
        ("neosoft2500", "96", "alarm_leakage_volume_no_shutoff"),
        ("triols", "9F", "alarm_end_switch"),
        ("syrsafetechlockconnect", "A0", "alarm_leak_protection_connection"),
        ("safetechplus", "AC", "alarm_increased_water_hardness"),
        ("safetechpluswifi", "AC", "alarm_conductivity_too_high"),
        ("safetechpluswifi", "A2", "alarm_no_network_connection"),
        ("hva", "A1", "alarm_safet_valve_cannot_be_operated"),
        ("hva", "A4", "alarm_heating_fill_flow_leak"),
        ("hva", "AC", "alarm_pressure_sensor_faulty"),
        ("inlinerhwa3300", "A8", "alarm_safet_48h_leakage"),
        ("controlicmini", "BA", "alarm_battery_low"),
        ("safetplus", "A7", "alarm_external_sensor_leakage_in2"),
    ],
)
def test_get_sensor_ala_map_family_codes(name: str, code: str, expected: str) -> None:
    """The alarm codes follow the table of the device family."""
    assert get_sensor_ala_map(_signature(name), code) == (expected, code)


def test_get_sensor_not_and_wrn_map_unmapped_and_none() -> None:
    """Test get sensor not and wrn map unmapped and none."""
    # unmapped code
    mapped_not, raw_not = get_sensor_not_map(UNKNOWN_MODEL, "ZZ")
    assert mapped_not is None and raw_not == "ZZ"

    # none input returns empty raw
    mapped_not2, raw_not2 = get_sensor_not_map(UNKNOWN_MODEL, None)
    assert mapped_not2 is None and raw_not2 == ""

    mapped_wrn, raw_wrn = get_sensor_wrn_map(UNKNOWN_MODEL, "ZZ")
    assert mapped_wrn is None and raw_wrn == "ZZ"


def test_get_sensor_ala_map_unrecognized_known_model() -> None:
    """A model without alarm codes of its family keeps the raw code."""
    model = replace(UNKNOWN_MODEL, name="futuredevice2100")
    assert get_sensor_ala_map(model, "FF") == (None, "FF")


def test_get_model_supported_keys_falls_back_without_device_profile() -> None:
    """A model without a device profile returns the global allowlist unchanged."""
    global_keys = {"getBAR", "getVOL"}
    assert get_model_supported_keys(UNKNOWN_MODEL, "sensor", global_keys) == global_keys


def test_get_model_supported_keys_uses_device_override_when_defined() -> None:
    """A devices/<name>.py file that defines the platform's allowlist is used verbatim.

    It replaces the global set.
    """

    global_keys = {"getBAR", "getVOL"}
    result = get_model_supported_keys(
        replace(UNKNOWN_MODEL, device_profile=muco_filling.PROFILE),
        "sensor",
        global_keys,
    )
    assert result == muco_filling.SENSOR_SUPPORTED_KEYS
    assert result != global_keys
    assert {"getCFT", "getCFV"} <= result

    result = get_model_supported_keys(
        replace(UNKNOWN_MODEL, device_profile=muco_connectioncentre.PROFILE),
        "sensor",
        global_keys,
    )
    assert result == muco_connectioncentre.SENSOR_SUPPORTED_KEYS
    assert {"getCFT", "getCFV"} <= result


def test_get_model_supported_keys_falls_back_when_platform_not_defined() -> None:
    """A device profile without this platform's allowlist falls back to the global set."""
    global_keys = {"getUPD"}
    # No device file defines an update allowlist, so the global set is returned unchanged.
    assert trio.PROFILE.update is None
    result = get_model_supported_keys(
        replace(UNKNOWN_MODEL, device_profile=trio.PROFILE), "update", global_keys
    )
    assert result is global_keys


def test_get_model_supported_keys_uses_shared_device_profile() -> None:
    """A rebrand uses the profile of the device file it shares with its siblings."""

    global_keys = {"getBAR"}
    result = get_model_supported_keys(
        _signature("sanibelleakprotect"),
        "sensor",
        global_keys,
    )
    assert result == muco_leakprotect.SENSOR_SUPPORTED_KEYS


def test_get_model_supported_keys_safetplus_device_override() -> None:
    """The safetplus model resolves its own devices/safetplus.py override file."""

    global_keys = {"getBAR"}
    result = get_model_supported_keys(
        replace(UNKNOWN_MODEL, device_profile=safetplus.PROFILE), "sensor", global_keys
    )
    assert result == safetplus.SENSOR_SUPPORTED_KEYS
    # Explicit empty-set override (no select-worthy keys) must be honored, not
    # treated as "not defined".
    assert (
        get_model_supported_keys(
            replace(UNKNOWN_MODEL, device_profile=safetplus.PROFILE),
            "select",
            global_keys,
        )
        == set()
    )


def test_get_model_supported_keys_safetech_device_override() -> None:
    """SafeTech and SafeTech+ models use their distinct allowlists."""

    safetech_names = {
        "safetech",
        "safetechv3",
        "safetechv4",
        "safetechpolygonvatro",
        "safetechrwc",
        "safetech141",
        "safetech145",
        "safetechpluswifi",
    }
    safetechplus_names = {"safetechplus"}
    model_names = safetech_names | safetechplus_names
    signatures = {
        signature.name: signature
        for signature in MODEL_SIGNATURES
        if signature.name in model_names
    }

    assert set(signatures) == model_names
    global_keys = {"getBAR", "getBAR2"}
    assert "getBAR" in safetech.SENSOR_SUPPORTED_KEYS
    assert "getBAR2" not in safetech.SENSOR_SUPPORTED_KEYS
    assert "getBAR" in safetechplus.SENSOR_SUPPORTED_KEYS
    assert "getBAR2" not in safetechplus.SENSOR_SUPPORTED_KEYS
    for names, module in (
        (safetech_names, safetech),
        (safetechplus_names, safetechplus),
    ):
        for name in names:
            signature = signatures[name]
            assert (
                get_model_supported_keys(signature, "sensor", global_keys)
                == module.SENSOR_SUPPORTED_KEYS
            )
        assert (
            get_model_supported_keys(
                signatures[next(iter(names))], "select", global_keys
            )
            == module.SELECT_SUPPORTED_KEYS
        )
        assert (
            get_model_supported_keys(
                signatures[next(iter(names))], "button", global_keys
            )
            == module.BUTTON_SUPPORTED_KEYS
        )


@pytest.mark.parametrize("platform", ["sensor", "select"])
def test_get_model_supported_keys_hva_without_rcp(platform: str) -> None:
    """The HVA does not get the synchronization interval (getRCP) of the global allowlists.

    On the HVA, getRCP is the remaining capacity, which the sensor and the select would
    show as synchronization interval.
    """
    signature = _signature("hva")
    global_keys = {"getBAR", "getRCP"}

    assert signature.device_profile is hva.PROFILE
    assert "getRCP" not in get_model_supported_keys(signature, platform, global_keys)


def test_get_model_supported_keys_lex_device_override() -> None:
    """The lex model resolves its own devices/lex.py override file.

    The file is shared by all l10-l100/lex10-lex100 signatures.
    """

    global_keys = {"getBAR"}
    result = get_model_supported_keys(
        replace(UNKNOWN_MODEL, device_profile=lex.PROFILE), "sensor", global_keys
    )
    assert result == lex.SENSOR_SUPPORTED_KEYS
    # No buzzer/valve on this model - explicit empty-set overrides honored.
    assert (
        get_model_supported_keys(
            replace(UNKNOWN_MODEL, device_profile=lex.PROFILE), "switch", global_keys
        )
        == set()
    )
    assert (
        get_model_supported_keys(
            replace(UNKNOWN_MODEL, device_profile=lex.PROFILE), "valve", global_keys
        )
        == set()
    )


def test_get_model_supported_keys_safefloor_device_override() -> None:
    """The safefloor model resolves its own devices/safefloor.py override file."""

    global_keys = {"getBAR"}
    result = get_model_supported_keys(
        replace(UNKNOWN_MODEL, device_profile=safefloor.PROFILE), "sensor", global_keys
    )
    assert result == safefloor.SENSOR_SUPPORTED_KEYS
    # This model has no display rotation, filling, or salt config selects, but its
    # alarm/humidity/temperature thresholds and sync/measurement intervals are
    # user-adjustable settings represented as select entities.
    assert (
        get_model_supported_keys(
            replace(UNKNOWN_MODEL, device_profile=safefloor.PROFILE),
            "select",
            global_keys,
        )
        == safefloor.SELECT_SUPPORTED_KEYS
    )
    assert (
        get_model_supported_keys(
            replace(UNKNOWN_MODEL, device_profile=safefloor.PROFILE),
            "valve",
            global_keys,
        )
        == set()
    )


def test_get_model_supported_keys_trio_device_override() -> None:
    """The trio model (Trio DFR/LS) resolves its own devices/trio.py override file."""

    global_keys = {"getBAR"}
    result = get_model_supported_keys(
        replace(UNKNOWN_MODEL, device_profile=trio.PROFILE), "sensor", global_keys
    )
    assert result == trio.SENSOR_SUPPORTED_KEYS
    assert "getDSV" in result
    assert "getSLF" in result


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        pytest.param("conelclearprofill", {"getLOT", "getOHW"}, id="muco-filling"),
        pytest.param("allinoneplus", {"getFCS", "getOWH"}, id="allinoneplus"),
        pytest.param("lex30", set(), id="softener"),
        pytest.param("unknown", set(), id="no-profile"),
    ],
)
def test_get_cartridge_keys(model: str, expected: set[str]) -> None:
    """The device profile names the keys that only apply to one cartridge type or size."""
    signature = UNKNOWN_MODEL if model == "unknown" else _signature(model)

    assert get_cartridge_keys(signature) == expected


_SYR_CONNECT_TEST_CARTRIDGE_KEYS = {"getFCS", "getLOT", "getOHW", "getOWH"}


@pytest.mark.parametrize(
    ("model", "status", "supported_keys", "expected"),
    [
        pytest.param(
            "conelclearprofill",
            {"getCRT": "1", "getLOT": "7"},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            {"getLOT"},
            id="hve",
        ),
        pytest.param(
            "conelclearprofill",
            {"getCRT": 2, "getLOT": "7"},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            {"getLOT"},
            id="hve-plus",
        ),
        pytest.param(
            "conelclearprofill",
            {"getCRT": "0", "getOHW": "3", "getOWH": "5"},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            {"getOHW"},
            id="hwe-muco",
        ),
        pytest.param(
            "allinoneplus",
            {"getCRT": "0", "getOHW": "3", "getOWH": "5"},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            {"getOWH"},
            id="hwe-allinoneplus",
        ),
        pytest.param(
            "allinoneplus",
            {"getCRT": "1", "getLOT": "7"},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            set(),
            id="allinoneplus-hve",
        ),
        pytest.param(
            "conelclearprofill",
            {"getCRT": "1", "getLOT": "7"},
            {"getOHW"},
            set(),
            id="not-listed",
        ),
        pytest.param(
            "conelclearprofill",
            {"getCRT": "0", "getOHW": ""},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            set(),
            id="hwe-empty",
        ),
        pytest.param(
            "conelclearprofill",
            {"getCRT": "1", "getLOT": None},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            set(),
            id="hve-missing",
        ),
        pytest.param(
            "conelclearprofill",
            {"getCRT": "", "getOHW": "3"},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            set(),
            id="no-cartridge",
        ),
        pytest.param(
            "conelclearprofill",
            {"getOHW": "3"},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            set(),
            id="no-crt",
        ),
        pytest.param(
            "unknown",
            {"getCRT": "1", "getLOT": "7"},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            set(),
            id="no-profile",
        ),
        pytest.param(
            "allinoneplus",
            {"getCRS": "0", "getFCS": "20"},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            {"getFCS"},
            id="custom-size",
        ),
        pytest.param(
            "allinoneplus",
            {"getCRS": "1", "getFCS": "20"},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            set(),
            id="fixed-size",
        ),
        pytest.param(
            "allinoneplus",
            {"getCRT": "0", "getOWH": "5", "getCRS": 0, "getFCS": "20"},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            {"getFCS", "getOWH"},
            id="hwe-and-custom-size",
        ),
        pytest.param(
            "conelclearprofill",
            {"getCRS": "0", "getFCS": "20"},
            _SYR_CONNECT_TEST_CARTRIDGE_KEYS,
            set(),
            id="muco-without-custom-size",
        ),
    ],
)
def test_get_cartridge_entity_keys(
    model: str, status: dict[str, Any], supported_keys: set[str], expected: set[str]
) -> None:
    """The keys of the cartridge type and size, if the model lists them and they have a value."""
    signature = UNKNOWN_MODEL if model == "unknown" else _signature(model)

    assert get_cartridge_entity_keys(signature, status, supported_keys) == expected


@pytest.mark.parametrize(
    ("model", "key", "raw_code", "expected"),
    [
        pytest.param("allinoneplus", "getIWH", "3", (10, 900, 10), id="ppm"),
        pytest.param("allinoneplus", "getOWH", 1, (0, 16, 1), id="e"),
        pytest.param("allinoneplus", "getOWH", "7", None, id="unknown-unit"),
        pytest.param("allinoneplus", "getOWH", None, None, id="no-unit"),
        pytest.param("lex30", "getIWH", "0", None, id="fixed-range"),
        pytest.param("unknown", "getIWH", "0", None, id="no-profile"),
    ],
)
def test_get_hardness_range(
    model: str, key: str, raw_code: Any, expected: tuple[int, int, int] | None
) -> None:
    """The profile names the water hardness range per unit (getWHU)."""
    signature = UNKNOWN_MODEL if model == "unknown" else _signature(model)

    assert get_hardness_range(signature, key, raw_code) == expected


@pytest.mark.parametrize(
    ("model", "raw_code", "expected"),
    [
        pytest.param("conelclearprofill", "0", 1.0, id="dh"),
        pytest.param("conelclearprofill", 1, 1.25216338, id="e"),
        pytest.param("conelclearprofill", "2.0", 1.78480457, id="fh"),
        pytest.param("conelclearprofill", "3", 17.8480457, id="ppm"),
        pytest.param("conelclearprofill", "7", 1.0, id="unknown-unit"),
        pytest.param("conelclearprofill", None, 1.0, id="no-unit"),
        pytest.param("allinoneplus", "3", 1.0, id="values-in-the-unit"),
        pytest.param("unknown", "3", 1.0, id="no-profile"),
    ],
)
def test_get_hardness_factor(model: str, raw_code: Any, expected: float) -> None:
    """Only a device that keeps the water hardness in °dH converts it to the unit."""
    signature = UNKNOWN_MODEL if model == "unknown" else _signature(model)

    assert get_hardness_factor(signature, raw_code) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, 0),
        (4.48, 4),
        (2.5, 3),
        (3.5, 4),
    ],
)
def test_round_hardness(value: float, expected: int) -> None:
    """A converted water hardness is rounded to a whole number, halves up."""
    assert round_hardness(value) == expected
