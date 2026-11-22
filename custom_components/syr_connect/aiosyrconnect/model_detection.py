"""Device model signatures of the SYR devices and their detection.

A signature tells how a model is detected (device kind of the cloud, status checks)
and how it is addressed (local path of the JSON API, alarm commands), and it names the
code tables of its family (`codes.py`).
`detect_model_signature()` selects the signature of a device from the cloud device
kind and its status, or None for an unknown model; `UNKNOWN_MODEL_SIGNATURE` names
such a model. The caller may pass signatures of its own that extend
`SyrConnectModelSignature`, in the order of `MODEL_SIGNATURES`.
"""

from collections.abc import Mapping, Sequence
import logging

from .codes import (
    ALA_CODES_ALLINONEPLUS,
    ALA_CODES_COMMON,
    ALA_CODES_DOSINGPUMP,
    ALA_CODES_HVA,
    ALA_CODES_HYGBOX,
    ALA_CODES_HYGIENEMODULE,
    ALA_CODES_LEX,
    ALA_CODES_LEXPLUS10SL,
    ALA_CODES_SAFEFLOOR,
    ALA_CODES_SAFETECH,
    ALA_CODES_SAFETPLUS,
    NOT_CODES_COMMON,
    NOT_CODES_NONE,
    WRN_CODES_COMMON,
    WRN_CODES_NONE,
)
from .models import SyrConnectModelSignature, SyrConnectStatistic
from .units import WHU_UNITS_LEX, WHU_UNITS_MUCO, WHU_UNITS_NEOSOFT

_LOGGER = logging.getLogger(__name__)

# Signature of a model that no signature matches: no device kind, no local path of the
# JSON API, generic names. It is not part of `MODEL_SIGNATURES`, so it is never detected.
UNKNOWN_MODEL_SIGNATURE = SyrConnectModelSignature(
    base_path=None,
    display_name="Unknown model",
    dk=None,
    dkv=None,
    manufacturer="Unknown",
    name="unknown",
)

# Cartridge type (getCRT) of the MuCo filling controller and connection centre -> key
# with the value of that cartridge
_CARTRIDGE_KEYS_MUCO_FILLING: Mapping[str, str] = {
    "0": "getOHW",
    "1": "getLOT",
    "2": "getLOT",
}

# Maximum temperature of the cold water line (getCCL) of the hygiene module in °C: 15-25
_CCL_VALUES_HYGIENEMODULE = range(15, 26)

# Maximum temperature of the cold water line (getCCL) of the Safe-T hygiene module in °C:
# 2-40
_CCL_VALUES_SAFETHYGIENEMODULE = range(2, 41)

# NeoSoft reports the water hardness in tenths of mmol/l (getWHU 1)
_HARDNESS_DIVISORS_NEOSOFT: Mapping[int, int] = {
    1: 10,
}

# Water hardness ranges of the All-in-One+ per unit: getWHU code -> (lowest, highest,
# step) in that unit. The soft water hardness (getOWH) can be at most the raw water
# hardness (getIWH).
_HARDNESS_RANGES_ALLINONEPLUS: Mapping[str, Mapping[int, tuple[int, int, int]]] = {
    "getIWH": {
        0: (1, 50, 1),  # °dH
        1: (1, 65, 1),  # °e
        2: (1, 90, 1),  # °fH
        3: (10, 900, 10),  # ppm
    },
    "getOWH": {
        0: (0, 12, 1),  # °dH
        1: (0, 16, 1),  # °e
        2: (0, 22, 1),  # °fH
        3: (0, 220, 10),  # ppm
    },
}

# Maximum duration of the initial filling (getFMT) of the MuCo filling controller and
# connection centre in minutes: 1-5 in steps of 1, 10, 15, 30, 45, 60-1500 in steps of
# 30
_FMT_VALUES_MUCO_FILLING = sorted(
    {
        *range(1, 6),
        10,
        15,
        30,
        45,
        *range(60, 1501, 30),
    }
)

# Water hardness ranges of the MuCo filling controller and connection centre per unit:
# getWHU code -> (lowest, highest, step) in that unit. The device keeps both values in
# °dH (`hardness_in_dh`), getWHU is only the unit of the display. The soft water hardness
# (getOHW) can be at most the raw water hardness (getIWH).
_HARDNESS_RANGES_MUCO_FILLING: Mapping[str, Mapping[int, tuple[int, int, int]]] = {
    "getIWH": {
        0: (1, 50, 1),  # °dH
        1: (1, 65, 1),  # °e
        2: (1, 90, 1),  # °fH
        3: (10, 900, 10),  # ppm
    },
    "getOHW": {
        0: (0, 12, 1),  # °dH
        1: (0, 16, 1),  # °e
        2: (0, 22, 1),  # °fH
        3: (0, 220, 10),  # ppm
    },
}

# Raw values of the hygiene module written for "off": 0 days for the periodic flushing,
# one degree below the range for the temperature limit
_OFF_VALUES_HYGIENEMODULE: Mapping[str, int] = {
    "getCCF": 0,
    "getCCL": 14,
    "getCWF": 0,
    "getWCL": 54,
}

# Raw values of the hygiene module of the cold water line written for "off"
_OFF_VALUES_HYGIENEMODULE_COLD: Mapping[str, int] = {
    "getCCF": 0,
    "getCCL": 14,
}

# Raw values of the hygiene module of the hot water line written for "off"
_OFF_VALUES_HYGIENEMODULE_HOT: Mapping[str, int] = {
    "getCWF": 0,
    "getWCL": 54,
}

# Raw values of the Safe-T hygiene module written for "off": 0 days for the periodic
# flushing
_OFF_VALUES_SAFETHYGIENEMODULE: Mapping[str, int] = {
    "getCCF": 0,
    "getCWF": 0,
}

# Raw values of the Safe-T hygiene module of the cold water line written for "off"
_OFF_VALUES_SAFETHYGIENEMODULE_COLD: Mapping[str, int] = {
    "getCCF": 0,
}

# Synchronization interval (getRCP) of the HygBox in seconds: 6 hours to 8 days, the
# steps of `SETTING_VALUES` within this range
_RCP_VALUES_HYGBOX = [
    21600,
    43200,
    86400,
    172800,
    259200,
    345600,
    432000,
    518400,
    604800,
    691200,
]

# Maximum filling duration (getRMT) of the All-in-One+ in minutes: 5-20 in steps of 5,
# 30-50 in steps of 10, 60-720 in steps of 30
_RMT_VALUES_ALLINONEPLUS = sorted(
    {
        *range(5, 21, 5),
        *range(30, 51, 10),
        *range(60, 721, 30),
    }
)

# The sensor measures every getWMP seconds but uploads only every getRCP seconds, so
# the status holds only the latest measurement. The cloud keeps the raw measurements
# of the last 6 days (see "SafeFloor measurement history" in docs/syrconnect-protocol.md).
_STATISTICS_SAFEFLOOR: tuple[SyrConnectStatistic, ...] = (
    SyrConnectStatistic(
        key="getCEL",
        method="GetSafeFloorStatistics",
        rtyp=4,
        t=1,
        unit="°C",
    ),
    SyrConnectStatistic(
        key="getHMD",
        method="GetSafeFloorStatistics",
        rtyp=4,
        t=2,
        unit="%",
    ),
)

# The LEX family reports the flow (getFLO) in l/min instead of l/h
_VALUE_FACTORS_FLOW_PER_MINUTE: Mapping[str, int] = {
    "getFLO": 60,
}

# Minimum temperature of the hot water line (getWCL) of the hygiene module in °C: 55-65
_WCL_VALUES_HYGIENEMODULE = range(55, 66)

# Minimum temperature of the hot water line (getWCL) of the Safe-T hygiene module in °C:
# 50-70
_WCL_VALUES_SAFETHYGIENEMODULE = range(50, 71)

# Signatures of the known models, derived from fixtures and the dkv table in
# docs/syrconnect-protocol.md. Each signature may include explicit checks (exact
# `getCNA` value, serial number or version patterns). The order matters: the status
# checks return the first signature that matches.
MODEL_SIGNATURES: tuple[SyrConnectModelSignature, ...] = (
    # ── Safe-T+ (dk=1) ──────────────────────────────────────────────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETPLUS,
        base_path=None,
        display_name="Safe-T+ Connect",
        dk=1,
        dkv=6,
        manufacturer="SYR",
        name="safetplus",
        ver_prefix="Safe-T+",
    ),
    # ── Safe-T Master / Slave / Communication module (dk=2, 3, 5) ──────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETPLUS,
        base_path=None,
        display_name="Safe-T Master",
        dk=2,
        dkv=2,
        manufacturer="SYR",
        name="safetmaster",
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETPLUS,
        base_path=None,
        display_name="Safe-T Slave",
        dk=3,
        dkv=3,
        manufacturer="SYR",
        name="safetslave",
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETPLUS,
        base_path=None,
        display_name="Safe-T Slave",
        dk=3,
        dkv=4,
        manufacturer="SYR",
        name="safetslaveinwall",
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETPLUS,
        base_path=None,
        display_name="Safe-T Communication Module",
        dk=5,
        dkv=12,
        manufacturer="SYR",
        name="safetcomm",
        # TODO: Untested model.
    ),
    # ── Safe-T Hygiene module (dk=4) ─────────────────────────────────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETPLUS,
        base_path=None,
        display_name="Safe-T Hygiene Module",
        dk=4,
        dkv=5,
        manufacturer="SYR",
        name="safethygienemodulecold",
        setting_off_values=_OFF_VALUES_SAFETHYGIENEMODULE_COLD,
        setting_values={
            "getCCL": _CCL_VALUES_SAFETHYGIENEMODULE,
        },
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETPLUS,
        base_path=None,
        display_name="Safe-T Hygiene Module",
        dk=4,
        dkv=11,
        manufacturer="SYR",
        name="safethygienemoduleinwall",
        setting_off_values=_OFF_VALUES_SAFETHYGIENEMODULE,
        setting_values={
            "getCCL": _CCL_VALUES_SAFETHYGIENEMODULE,
            "getWCL": _WCL_VALUES_SAFETHYGIENEMODULE,
        },
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETPLUS,
        base_path=None,
        display_name="Safe-T Hygiene Module",
        dk=4,
        dkv=15,
        manufacturer="SYR",
        name="safethygienemodule",
        setting_off_values=_OFF_VALUES_SAFETHYGIENEMODULE,
        setting_values={
            "getCCL": _CCL_VALUES_SAFETHYGIENEMODULE,
            "getWCL": _WCL_VALUES_SAFETHYGIENEMODULE,
        },
        # TODO: Untested model.
    ),
    # ── HVA (dk=20) ─────────────────────────────────────────────────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_HVA,
        base_path=None,
        display_name="HVA",
        dk=20,
        dkv=19,
        manufacturer="SYR",
        name="hva",
        not_codes=NOT_CODES_NONE,
        wrn_codes=WRN_CODES_NONE,
        # TODO: Untested model.
    ),
    # ── Inliner-HWA 3300 (dk=25) ─────────────────────────────────────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETPLUS,
        base_path=None,
        display_name="Inliner-HWA 3300",
        dk=25,
        dkv=26,
        manufacturer="SYR",
        name="inlinerhwa3300",
        # TODO: Untested model.
    ),
    # ── i-LEX / LEX (dk=40, dkv=16) ─────────────────────────────────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L10",
        display_name="i-LEX 10 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR Oceanic",
        maximum_regeneration_interval=99,
        maximum_salt_volume=25,
        name="l10",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L12",
        display_name="i-LEX 12 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR Oceanic",
        maximum_regeneration_interval=99,
        maximum_salt_volume=25,
        name="l12",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L15",
        display_name="i-LEX 15 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR Oceanic",
        maximum_regeneration_interval=99,
        maximum_salt_volume=25,
        name="l15",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L20",
        display_name="i-LEX 20 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR Oceanic",
        maximum_regeneration_interval=99,
        maximum_salt_volume=70,
        name="l20",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L25",
        display_name="i-LEX 25 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR Oceanic",
        maximum_regeneration_interval=99,
        maximum_salt_volume=70,
        name="l25",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L30",
        display_name="i-LEX 30 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR Oceanic",
        maximum_regeneration_interval=99,
        maximum_salt_volume=70,
        name="l30",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L40",
        display_name="i-LEX 40 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR Oceanic",
        maximum_regeneration_interval=99,
        maximum_salt_volume=75,
        name="l40",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L50",
        display_name="i-LEX 50 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR Oceanic",
        maximum_regeneration_interval=99,
        maximum_salt_volume=75,
        name="l50",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L60",
        display_name="i-LEX 60 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR Oceanic",
        maximum_regeneration_interval=99,
        maximum_salt_volume=110,
        name="l60",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L70",
        display_name="i-LEX 70 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR Oceanic",
        maximum_regeneration_interval=99,
        maximum_salt_volume=110,
        name="l70",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L80",
        display_name="i-LEX 80 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR Oceanic",
        maximum_regeneration_interval=99,
        maximum_salt_volume=200,
        name="l80",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L90",
        display_name="i-LEX 90 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR Oceanic",
        maximum_regeneration_interval=99,
        maximum_salt_volume=200,
        name="l90",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="L100",
        display_name="i-LEX 100 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR Oceanic",
        maximum_regeneration_interval=99,
        maximum_salt_volume=300,
        name="l100",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX10",
        display_name="LEX 10 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR",
        maximum_regeneration_interval=99,
        maximum_salt_volume=25,
        name="lex10",
        not_codes=NOT_CODES_NONE,
        sbt=1,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX20",
        display_name="LEX 20 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR",
        maximum_regeneration_interval=99,
        maximum_salt_volume=70,
        name="lex20",
        not_codes=NOT_CODES_NONE,
        sbt=2,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX30",
        display_name="LEX 30 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR",
        maximum_regeneration_interval=99,
        maximum_salt_volume=70,
        name="lex30",
        not_codes=NOT_CODES_NONE,
        sbt=3,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX40",
        display_name="LEX 40 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR",
        maximum_regeneration_interval=99,
        maximum_salt_volume=75,
        name="lex40",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX60",
        display_name="LEX 60 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR",
        maximum_regeneration_interval=99,
        maximum_salt_volume=110,
        name="lex60",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX80",
        display_name="LEX 80 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR",
        maximum_regeneration_interval=99,
        maximum_salt_volume=200,
        name="lex80",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEX100",
        display_name="LEX 100 Connect",
        dk=40,
        dkv=16,
        manufacturer="SYR",
        maximum_regeneration_interval=99,
        maximum_salt_volume=300,
        name="lex100",
        not_codes=NOT_CODES_NONE,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    # ── Hygiene module (dk=60-63) ────────────────────────────────────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_HYGIENEMODULE,
        base_path=None,
        display_name="Hygiene Module (cold)",
        dk=60,
        dkv=21,
        manufacturer="SYR",
        name="hygienemodulecold",
        setting_off_values=_OFF_VALUES_HYGIENEMODULE_COLD,
        setting_values={
            "getCCL": _CCL_VALUES_HYGIENEMODULE,
        },
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_HYGIENEMODULE,
        base_path=None,
        display_name="Hygiene Module (hot)",
        dk=61,
        dkv=22,
        manufacturer="SYR",
        name="hygienemodulehot",
        setting_off_values=_OFF_VALUES_HYGIENEMODULE_HOT,
        setting_values={
            "getWCL": _WCL_VALUES_HYGIENEMODULE,
        },
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_HYGIENEMODULE,
        base_path=None,
        display_name="Hygiene Module (hot and cold)",
        dk=62,
        dkv=23,
        manufacturer="SYR",
        name="hygienemodulehotcold",
        setting_off_values=_OFF_VALUES_HYGIENEMODULE,
        setting_values={
            "getCCL": _CCL_VALUES_HYGIENEMODULE,
            "getWCL": _WCL_VALUES_HYGIENEMODULE,
        },
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_HYGIENEMODULE,
        base_path=None,
        display_name="Hygiene Module (cold and hot)",
        dk=63,
        dkv=24,
        manufacturer="SYR",
        name="hygienemodulecoldhot",
        setting_off_values=_OFF_VALUES_HYGIENEMODULE,
        setting_values={
            "getCCL": _CCL_VALUES_HYGIENEMODULE,
            "getWCL": _WCL_VALUES_HYGIENEMODULE,
        },
        # TODO: Untested model.
    ),
    # ── LEX Plus 10 (dk=80, dkv=25) ─────────────────────────────────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEXplus10",
        display_name="LEX Plus 10 Connect",
        dk=80,
        dkv=25,
        local_time_timestamps=True,
        manufacturer="SYR",
        maximum_regeneration_interval=4,
        maximum_salt_volume=25,
        name="lexplus10",
        not_codes=NOT_CODES_NONE,
        sbt=1,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEX,
        alarm_style_alm=True,
        base_path=None,
        cna_equals="LEXplus10S",
        display_name="LEX Plus 10 S Connect",
        dk=80,
        dkv=25,
        local_time_timestamps=True,
        manufacturer="SYR",
        maximum_regeneration_interval=4,
        maximum_salt_volume=25,
        name="lexplus10s",
        not_codes=NOT_CODES_NONE,
        sbt=2,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_LEXPLUS10SL,
        # False (getALA), unlike its lexplus10/lexplus10s siblings: this
        # fixture reports getALA, not getALM, as the current alarm code.
        alarm_style_alm=False,
        base_path=None,
        cna_equals="LEXplus10SL",
        display_name="LEX Plus 10 SL Connect",
        dk=80,
        dkv=25,
        local_time_timestamps=True,
        manufacturer="SYR",
        maximum_regeneration_interval=4,
        maximum_salt_volume=25,
        name="lexplus10sl",
        not_codes=NOT_CODES_NONE,
        sbt=7,
        value_factors=_VALUE_FACTORS_FLOW_PER_MINUTE,
        ver_prefix=None,
        whu_units=WHU_UNITS_LEX,
    ),
    # ── CONTROLICmini (dk=100) ───────────────────────────────────────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETPLUS,
        base_path=None,
        display_name="CONTROLICmini",
        dk=100,
        dkv=27,
        manufacturer="SYR",
        name="controlicmini",
        # TODO: Untested model.
    ),
    # ── SafeFloor (dk=120/122) ───────────────────────────────────────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFEFLOOR,
        # dk=120/dkv=34 is shared by multiple vendors; the cloud service tells them
        # apart (`service_branding`).
        base_path=None,
        bat_in_percent=True,
        display_name="SafeFloor Connect",
        dk=120,
        dkv=34,
        manufacturer="SYR",
        name="safefloor",
        service_branding={
            # CLEAR PRO Bodensensor
            "de.consoft.gc.conel.connect": (
                "CONEL",
                "CLEAR PRO Floor Sensor",
            ),
            # Funk Boden sensor A25
            "de.consoft.gsh.comfort.connect": (
                "Sanibel",
                "Wireless Floor Sensor A25",
            ),
            # 2422.00.100 - concept SafeFloor Bodensensor für den SafeTech Connect 2422
            "de.consoft.isg.concept.connect": (
                "CONCEPT",
                "concept SafeFloor Floor Sensor",
            ),
            # Optima T2 Bodensensor
            "de.consoft.isg.optima.connect": (
                "OPTIMA",
                "Optima T2 Floor Sensor",
            ),
            # POLYGONVATRO Funk-Bodensensor
            "de.consoft.polygonvatro.connect": (
                "POLYGONVATRO",
                "Wireless Floor Sensor",
            ),
            # DITECH Funk-Bodensensor
            "de.consoft.sanitaerunion.ditech.connect": (
                "DITECH",
                "Ditech Wireless Floor Sensor",
            ),
        },
        statistics=_STATISTICS_SAFEFLOOR,
        ver_contains="Floorsensor",
        ver_prefix=None,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFEFLOOR,
        base_path=None,
        bat_in_percent=True,
        display_name="MultiSafe Floor Leak Sensor",
        dk=120,
        dkv=43,
        manufacturer="Reliance Valves",
        name="safefloorrwc",
        # TODO: Untested model.
        srn_prefix="43",
        statistics=_STATISTICS_SAFEFLOOR,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFEFLOOR,
        base_path=None,
        bat_in_percent=True,
        display_name="SafeFloor Connect",
        dk=122,
        dkv=34,
        manufacturer="SYR",
        name="safefloor122",
        statistics=_STATISTICS_SAFEFLOOR,
        # TODO: Untested model.
    ),
    # ── SafeTech / SafeTech+ (dk=140/141/142/145) ────────────────────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETECH,
        base_path="/trio",
        display_name="SafeTech Connect",
        dk=140,
        dkv=35,
        manufacturer="SYR",
        name="safetech",
        not_codes=NOT_CODES_NONE,
        # TODO: Untested model. Both values are incorrect in fixture.
        srn_infix="aBC",
        srn_prefix="123",
        wrn_codes=WRN_CODES_NONE,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETECH,
        base_path="/safe-tec",
        display_name="SafeTech V3 Connect",
        dk=140,
        dkv=35,
        manufacturer="SYR",
        name="safetechv3",
        not_codes=NOT_CODES_NONE,
        ver_prefix="Safe-Tech V3",
        wrn_codes=WRN_CODES_NONE,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETECH,
        base_path="/safe-tec",
        display_name="SafeTech V4 Connect",
        dk=140,
        dkv=35,
        manufacturer="SYR",
        name="safetechv4",
        not_codes=NOT_CODES_NONE,
        ver_prefix="Safe-Tech V4",
        wrn_codes=WRN_CODES_NONE,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETECH,
        # POLYGONVATRO sold these "SYR Safe-Tech Connect" devices together
        # with the AXA building insurance, called "Wasserwächter". Order.-No.: 2422.25.003
        base_path=None,
        display_name="Water Monitor",
        # base_path="/safe-tec",
        dk=140,
        dkv=38,
        manufacturer="POLYGONVATRO",
        name="safetechpolygonvatro",
        not_codes=NOT_CODES_NONE,
        wrn_codes=WRN_CODES_NONE,
        # TODO: Untested model.
        # srn_prefix="38",
        # Version string: "Safe-Tech V3.53", see https://www.youtube.com/watch?v=apdL8SLZ64Q&t=585s
        # The device reports a version string that looks like "Safe-Tech V4.08" firmware installed.
        # ver_prefix="Safe-Tech V3",
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETECH,
        base_path="/safe-tec",
        display_name="MultiSafe Leak Detector Control Valve",
        dk=140,
        dkv=42,
        manufacturer="Reliance Valves",
        name="safetechrwc",
        not_codes=NOT_CODES_NONE,
        # TODO: Untested model.
        srn_prefix="42",
        wrn_codes=WRN_CODES_NONE,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETECH,
        base_path="/pontos-base",
        display_name="Pontos Base",
        dk=140,
        dkv=None,
        manufacturer="Hansgrohe",
        name="pontosbase",
        not_codes=NOT_CODES_NONE,
        # TODO: Untested model.
        ver_prefix="PontosBase",
        wrn_codes=WRN_CODES_NONE,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETECH,
        base_path=None,
        display_name="SafeTech Connect",
        # base_path="/safe-tec",
        dk=141,
        dkv=35,
        manufacturer="SYR",
        name="safetech141",
        not_codes=NOT_CODES_NONE,
        wrn_codes=WRN_CODES_NONE,
        # TODO: Untested model.
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETECH,
        base_path=None,
        display_name="SafeTech+ Connect",
        dk=142,
        dkv=39,
        manufacturer="SYR",
        name="safetechpluswifi",
        not_codes=NOT_CODES_NONE,
        # TODO: Untested model.
        srn_prefix="39",
        wrn_codes=WRN_CODES_NONE,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_SAFETECH,
        base_path=None,
        display_name="SafeTech Connect",
        # base_path="/safe-tec",
        dk=145,
        dkv=35,
        manufacturer="SYR",
        name="safetech145",
        not_codes=NOT_CODES_NONE,
        wrn_codes=WRN_CODES_NONE,
        # TODO: Untested model.
    ),
    # ── Specialty devices (dk=160/180/190) ───────────────────────────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_ALLINONEPLUS,
        bar_is_system_pressure=True,
        # Product number: 3228.15.015
        base_path="/all-in-one",
        cartridge_keys={
            "0": "getOWH",
        },
        cartridge_size_keys={
            "0": "getFCS",
        },
        display_name="All-in-One+",
        dk=160,
        dkv=36,
        hardness_ranges=_HARDNESS_RANGES_ALLINONEPLUS,
        # The automatic filling mode (getDFI) is 0 = enabled, 1 = disabled
        inverted_flags={
            "getDFI",
        },
        manufacturer="SYR",
        name="allinoneplus",
        setting_values={
            "getRMT": _RMT_VALUES_ALLINONEPLUS,
        },
        value_divisors={
            "getCFV": 1000,
            "getLFV": 1000,
        },
        ver_prefix="All-in-One+",
        whu_units=WHU_UNITS_MUCO,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_HYGBOX,
        base_path="/hygbox",
        display_name="HygBox",
        dk=180,
        dkv=37,
        # The flushings (getFD1-3) report the function as disabled
        inverted_flags={
            "getFD1",
            "getFD2",
            "getFD3",
        },
        manufacturer="SYR",
        name="hygbox",
        service_branding={
            # DT3638 - DITECH Hygienespülbox
            "de.consoft.sanitaerunion.ditech.connect": (
                "DITECH",
                "DITECH Hygiene Flush Box",
            ),
        },
        setting_values={
            "getRCP": _RCP_VALUES_HYGBOX,
        },
        # TODO: Untested model.
        srn_prefix="37",
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_DOSINGPUMP,
        base_path="/dosing-pump",
        display_name="Dosing Pump",
        dk=190,
        dkv=44,
        manufacturer="SYR",
        name="dosingpump",
        # TODO: Untested model.
        # Probably the SYR NeoDos Connect; not yet confirmed by the manufacturer.
        # Unverified serial prefix from documentation, missing infix 'AAA' and match condition.
        srn_prefix="2031",
    ),
    # ── Trio LS platform (dk=1100-1113) ──────────────────────────────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        display_name="Trio LS Connect",
        dk=1100,
        dkv=100,
        manufacturer="SYR",
        name="triols",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="100",
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        display_name="concept 200 Replacement Filter",
        dk=1110,
        dkv=110,
        manufacturer="CONCEPT",
        name="concept200replacementfilter",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="110",
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        display_name="Optima T Replacement Filter",
        dk=1111,
        dkv=111,
        manufacturer="OPTIMA",
        name="optimatreplacementfilter",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="111",
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        display_name="SafeTech Plus Connect",
        dk=1112,
        dkv=112,
        manufacturer="SYR",
        name="safetechplus",
        not_codes=NOT_CODES_COMMON,
        srn_prefix="112",
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        display_name="Trio DFR/LS Connect",
        dk=1113,
        dkv=113,
        manufacturer="SYR",
        name="trio",
        not_codes=NOT_CODES_COMMON,
        srn_prefix="113",
        wrn_codes=WRN_CODES_COMMON,
    ),
    # ── NeoSoft platform (dk=1200-1222) ──────────────────────────────────────────
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # 5000.00.000 - SYR NeoSoft 5000 Connect
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="NeoSoft 5000 Connect",
        dk=1200,
        dkv=200,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="SYR",
        maximum_regeneration_interval=3,
        name="neosoft5000",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="200",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # 2500.00.000 - SYR NeoSoft 2500 Connect
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="NeoSoft 2500 Connect",
        dk=1206,
        dkv=206,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="SYR",
        maximum_regeneration_interval=3,
        name="neosoft2500",
        not_codes=NOT_CODES_COMMON,
        srn_prefix="206",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="comfort-Softwater UNO A25",
        dk=1207,
        dkv=207,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="Sanibel",
        maximum_regeneration_interval=3,
        name="sanibelsoftwateruno",
        not_codes=NOT_CODES_COMMON,
        srn_prefix="207",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="concept Single Water Softener",
        dk=1208,
        dkv=208,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="CONCEPT",
        maximum_regeneration_interval=3,
        name="conceptsingle",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="208",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="Optima Single Water Softener",
        dk=1209,
        dkv=209,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="OPTIMA",
        maximum_regeneration_interval=3,
        name="optimasingle",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="209",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="concept 200 Dual Water Softener",
        dk=1210,
        dkv=210,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="CONCEPT",
        maximum_regeneration_interval=3,
        name="concept200duo",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="210",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # 5000.02.700 - Optima T2.3 Doppelenthärtungsanlage, identical to the NeoSoft 5000
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="Optima T2 Dual Water Softener",
        dk=1211,
        dkv=211,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="OPTIMA",
        maximum_regeneration_interval=3,
        name="optimat2duo",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="211",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="comfort-Softwater DUO A25",
        dk=1212,
        dkv=212,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="Sanibel",
        maximum_regeneration_interval=3,
        name="sanibelsoftwaterduo",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="212",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="Optima Dual Water Softener",
        dk=1213,
        dkv=213,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="OPTIMA",
        maximum_regeneration_interval=3,
        name="optimaduo",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="213",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="CLEAR PRO SOFT TWIN",
        dk=1214,
        dkv=214,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="CONEL",
        maximum_regeneration_interval=3,
        name="conelclearprosofttwin",
        not_codes=NOT_CODES_COMMON,
        srn_prefix="214",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="CLEAR PRO SOFT",
        dk=1215,
        dkv=215,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="CONEL",
        maximum_regeneration_interval=3,
        name="conelclearprosoft",
        not_codes=NOT_CODES_COMMON,
        srn_prefix="215",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # 5000.02.100 - concept 300 Doppelenthärtungsanlage
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="concept Dual Water Softener",
        dk=1216,
        dkv=216,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="CONCEPT",
        maximum_regeneration_interval=3,
        name="conceptduo",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="216",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # DT3674 - DITECH Doppelenthärtungsanlage
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="DITECH Dual Water Softener",
        dk=1217,
        dkv=217,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="DITECH",
        maximum_regeneration_interval=3,
        name="ditechduo",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="217",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="TAKE Dual Water Softener",
        dk=1218,
        dkv=218,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="TAKE",
        maximum_regeneration_interval=3,
        name="takeduo",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="218",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # DT3673 - DITECH Einzelenthärtungsanlage
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="DITECH Single Water Softener",
        dk=1219,
        dkv=219,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="DITECH",
        maximum_regeneration_interval=3,
        name="ditechsingle",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="219",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="TAKE Single Water Softener",
        dk=1220,
        dkv=220,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="TAKE",
        maximum_regeneration_interval=3,
        name="takesingle",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="220",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # 5000.02.000 - SYR BLACKLANE - NeoSoft Lock Connect II, Doppelenthärtungsanlage
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="NeoSoft Lock Connect II",
        dk=1221,
        dkv=221,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="SYR",
        maximum_regeneration_interval=3,
        name="neosoftlock2",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="221",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # 2500.02.000 - SYR BLACKLANE - NeoSoft Lock Connect I, Einzelenthärtungsanlage
        alarm_clear_via_set=True,
        base_path="/neosoft",
        display_name="NeoSoft Lock Connect I",
        dk=1222,
        dkv=222,
        hardness_divisors=_HARDNESS_DIVISORS_NEOSOFT,
        manufacturer="SYR",
        maximum_regeneration_interval=3,
        name="neosoftlock1",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="222",
        whu_units=WHU_UNITS_NEOSOFT,
        wrn_codes=WRN_CODES_COMMON,
    ),
    # ── MultiController platform (dk=1500-1506) ──────────────────────────────────
    # The role of a MultiController is getDFM: 1 leak protection, 2 connection centre,
    # 3 All-in-One (dkv 500/506 only), 4 automatic backwash, 5 leak protection with
    # backwash filter (dkv 502-506 only). There is deliberately no generic signature for
    # an unknown role: such a device stays an unknown model, so it gets reported
    # instead of silently showing the global allowlists.
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # CLEARPNLS - Retrofit Leakage Protection
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        display_name="CLEAR PRO RETROFIT LEAKAGE PROTECTION",
        dk=1500,
        dkv=500,
        manufacturer="CONEL",
        name="conelclearproleakprotection",
        not_codes=NOT_CODES_COMMON,
        srn_prefix="500",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        cartridge_keys=_CARTRIDGE_KEYS_MUCO_FILLING,
        dfm=2,
        display_name="CLEAR PRO FILL",
        dk=1500,
        dkv=500,
        hardness_in_dh=True,
        hardness_ranges=_HARDNESS_RANGES_MUCO_FILLING,
        manufacturer="CONEL",
        name="conelclearproconnectioncentre",
        not_codes=NOT_CODES_COMMON,
        setting_values={
            "getFMT": _FMT_VALUES_MUCO_FILLING,
        },
        # TODO: Untested model.
        srn_prefix="500",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # CLEARPFSA - Filling Station
        alarm_clear_via_set=True,
        base_path="/trio",
        cartridge_keys=_CARTRIDGE_KEYS_MUCO_FILLING,
        dfm=3,
        display_name="CLEAR PRO FILL All-in-One",
        dk=1500,
        dkv=500,
        hardness_in_dh=True,
        hardness_ranges=_HARDNESS_RANGES_MUCO_FILLING,
        manufacturer="CONEL",
        name="conelclearprofill",
        not_codes=NOT_CODES_COMMON,
        setting_values={
            "getFMT": _FMT_VALUES_MUCO_FILLING,
        },
        srn_prefix="500",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # CLEARPMCK - MultiControl-Kit / Backwash System
        # TODO: Untested model.
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        display_name="CLEAR PRO MULTICONTROL-KIT",
        dk=1500,
        dkv=500,
        manufacturer="CONEL",
        name="conelclearprobackwash",
        not_codes=NOT_CODES_COMMON,
        srn_prefix="500",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        display_name="comfort-Leak Protection Module A25",
        dk=1501,
        dkv=501,
        manufacturer="Sanibel",
        name="sanibelleakprotect",
        not_codes=NOT_CODES_COMMON,
        srn_prefix="501",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        cartridge_keys=_CARTRIDGE_KEYS_MUCO_FILLING,
        dfm=2,
        display_name="comfort-Connection Module Plus Connect",
        dk=1501,
        dkv=501,
        hardness_in_dh=True,
        hardness_ranges=_HARDNESS_RANGES_MUCO_FILLING,
        manufacturer="Sanibel",
        name="sanibelconnectioncentre",
        not_codes=NOT_CODES_COMMON,
        setting_values={
            "getFMT": _FMT_VALUES_MUCO_FILLING,
        },
        # TODO: Untested model.
        srn_prefix="501",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        display_name="comfort-Automatic Backwash System RSA A25",
        dk=1501,
        dkv=501,
        manufacturer="Sanibel",
        name="sanibelrsa",
        not_codes=NOT_CODES_COMMON,
        srn_prefix="501",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        display_name="DITECH Leak Protection",
        dk=1502,
        dkv=502,
        manufacturer="DITECH",
        name="ditechleakprotect",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="502",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # DT3645 - DITECH Anschlussmodul Plus, with DT3646 - DITECH MultiControl
        alarm_clear_via_set=True,
        base_path="/trio",
        cartridge_keys=_CARTRIDGE_KEYS_MUCO_FILLING,
        dfm=2,
        display_name="DITECH Connection Module Plus",
        dk=1502,
        dkv=502,
        hardness_in_dh=True,
        hardness_ranges=_HARDNESS_RANGES_MUCO_FILLING,
        manufacturer="DITECH",
        name="ditechconnectioncentre",
        not_codes=NOT_CODES_COMMON,
        setting_values={
            "getFMT": _FMT_VALUES_MUCO_FILLING,
        },
        # TODO: Untested model.
        srn_prefix="502",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # DT3654 - DITECH Rückspülautomatik HWS/RF
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        display_name="DITECH Automatic Backwash HWS/RF",
        dk=1502,
        dkv=502,
        manufacturer="DITECH",
        name="ditechbackwash",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="502",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # DT3676 - DITECH Rückspülfilter Protect
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=5,
        display_name="DITECH Backwash Filter Protect",
        dk=1502,
        dkv=502,
        manufacturer="DITECH",
        name="ditechbackwashfilter",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="502",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        display_name="Leak Protection",
        dk=1503,
        dkv=503,
        manufacturer="TAKE",
        name="takeleakprotect",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="503",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        cartridge_keys=_CARTRIDGE_KEYS_MUCO_FILLING,
        dfm=2,
        display_name="Connection Module Plus",
        dk=1503,
        dkv=503,
        hardness_in_dh=True,
        hardness_ranges=_HARDNESS_RANGES_MUCO_FILLING,
        manufacturer="TAKE",
        name="takeconnectioncentre",
        not_codes=NOT_CODES_COMMON,
        setting_values={
            "getFMT": _FMT_VALUES_MUCO_FILLING,
        },
        # TODO: Untested model.
        srn_prefix="503",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        display_name="Automatic Backwash for HWS/RF",
        dk=1503,
        dkv=503,
        manufacturer="TAKE",
        name="takebackwash",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="503",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=5,
        display_name="Backwash Filter with Pressure Reducer and Leak Protection",
        dk=1503,
        dkv=503,
        manufacturer="TAKE",
        name="takebackwashfilter",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="503",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        display_name="concept 300 Leak Protection",
        dk=1504,
        dkv=504,
        manufacturer="CONCEPT",
        name="conceptleakprotect",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="504",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        cartridge_keys=_CARTRIDGE_KEYS_MUCO_FILLING,
        dfm=2,
        display_name="concept 300 Connection Module Plus",
        dk=1504,
        dkv=504,
        hardness_in_dh=True,
        hardness_ranges=_HARDNESS_RANGES_MUCO_FILLING,
        manufacturer="CONCEPT",
        name="conceptconnectioncentre",
        not_codes=NOT_CODES_COMMON,
        setting_values={
            "getFMT": _FMT_VALUES_MUCO_FILLING,
        },
        # TODO: Untested model.
        srn_prefix="504",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # 2380.01.104 - concept 300 Rückspülautomatik RSA
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        display_name="concept 300 Automatic Backwash RSA",
        dk=1504,
        dkv=504,
        manufacturer="CONCEPT",
        name="conceptbackwash",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="504",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # 2425.01.100 - concept 300 Triofilter mit Leckageschutz
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=5,
        display_name="concept 300 Trio Filter with Leak Protection",
        dk=1504,
        dkv=504,
        manufacturer="CONCEPT",
        name="concepttriolock",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="504",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        display_name="Optima T2 Leak Protection",
        dk=1505,
        dkv=505,
        manufacturer="OPTIMA",
        name="optimaleakprotect",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="505",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        cartridge_keys=_CARTRIDGE_KEYS_MUCO_FILLING,
        dfm=2,
        display_name="Optima T2 Connection Module Plus",
        dk=1505,
        dkv=505,
        hardness_in_dh=True,
        hardness_ranges=_HARDNESS_RANGES_MUCO_FILLING,
        manufacturer="OPTIMA",
        name="optimaconnectioncentre",
        not_codes=NOT_CODES_COMMON,
        setting_values={
            "getFMT": _FMT_VALUES_MUCO_FILLING,
        },
        # TODO: Untested model.
        srn_prefix="505",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # 2380.01.704 - Optima T2.3 Rückspülautomatik RSA
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        display_name="Optima T2 Automatic Backwash RSA",
        dk=1505,
        dkv=505,
        manufacturer="OPTIMA",
        name="optimabackwash",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="505",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        # 2425.01.700 - Optima T2.3 Leckageschutz und Rückspülfilter TRIO mit Druckminderer und Lock Flansch
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=5,
        display_name="Optima T2 Leak Protection and Backwash Filter TRIO",
        dk=1505,
        dkv=505,
        manufacturer="OPTIMA",
        name="optimatriolock",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="505",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=1,
        display_name="SafeTech Lock Connect",
        dk=1506,
        dkv=506,
        manufacturer="SYR",
        name="syrsafetechlockconnect",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="506",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        cartridge_keys=_CARTRIDGE_KEYS_MUCO_FILLING,
        dfm=2,
        display_name="AC 3200 Connect",
        dk=1506,
        dkv=506,
        hardness_in_dh=True,
        hardness_ranges=_HARDNESS_RANGES_MUCO_FILLING,
        manufacturer="SYR",
        name="syrac3200connect",
        not_codes=NOT_CODES_COMMON,
        setting_values={
            "getFMT": _FMT_VALUES_MUCO_FILLING,
        },
        # TODO: Untested model.
        srn_prefix="506",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        cartridge_keys=_CARTRIDGE_KEYS_MUCO_FILLING,
        dfm=3,
        display_name="AC All-in-One 3228 Connect",
        dk=1506,
        dkv=506,
        hardness_in_dh=True,
        hardness_ranges=_HARDNESS_RANGES_MUCO_FILLING,
        manufacturer="SYR",
        name="syrac3228connect",
        not_codes=NOT_CODES_COMMON,
        setting_values={
            "getFMT": _FMT_VALUES_MUCO_FILLING,
        },
        # TODO: Untested model.
        srn_prefix="506",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=4,
        display_name="RSA Connect",
        dk=1506,
        dkv=506,
        manufacturer="SYR",
        name="syrrsaconnect",
        not_codes=NOT_CODES_COMMON,
        # TODO: Untested model.
        srn_prefix="506",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
    SyrConnectModelSignature(
        ala_codes=ALA_CODES_COMMON,
        alarm_clear_via_set=True,
        base_path="/trio",
        dfm=5,
        display_name="TRIO Lock Connect",
        dk=1506,
        dkv=506,
        manufacturer="SYR",
        name="syrtriolockconnect",
        not_codes=NOT_CODES_COMMON,
        srn_prefix="506",
        whu_units=WHU_UNITS_MUCO,
        wrn_codes=WRN_CODES_COMMON,
    ),
)


def detect_model_signature[S: SyrConnectModelSignature](
    status: object,
    signatures: Sequence[S],
    dk: int | None = None,
    dkv: int | None = None,
    sbt: int | None = None,
) -> S | None:
    """Detect the signature of a device from the cloud device kind and its status.

    The cloud API (XML) reports `dk`, `dkv` and `sbt` for every device. They are the
    most reliable match and select the family of signatures with these values; a
    signature without `sbt` matches every subtype. A MultiController reports its role
    in getDFM, the subtype of dk=1500-1506: like `sbt`, a signature with
    `dfm` only matches a device with that role, one without `dfm` every device. A
    family of one signature is the result. In a larger family the status decides, but
    only between its signatures (getCNA for the i-LEX sizes, getVER for SafeTech
    V3/V4). Without a family, e.g. for the local JSON API that has no device kind or
    for a device kind no signature knows, the status decides between all signatures.

    Args:
        status: Flattened device status
        signatures: The signatures to choose from, e.g. `MODEL_SIGNATURES`
        dk: Cloud API deviceKind, None if unknown
        dkv: Cloud API deviceKindVersion, None if unknown
        sbt: Cloud API device subtype, None if unknown

    Returns:
        The matched signature, or None if no signature matches.
    """
    # getDFM is text in the cloud status and a number in the local status
    dfm = str(status.get("getDFM")) if isinstance(status, dict) else None
    candidates = [sig for sig in signatures if sig.dfm is None or str(sig.dfm) == dfm]
    if dk is not None:
        family = [
            sig
            for sig in candidates
            if sig.dk == dk and sig.dkv == dkv and sig.sbt in (None, sbt)
        ]
        if len(family) == 1:
            _LOGGER.debug(
                "Matched signature %s (dk=%s, dkv=%s, sbt=%s, dfm=%s)",
                family[0].name,
                dk,
                dkv,
                sbt,
                dfm,
            )
            return family[0]
        if family:
            return _match_status_values(status, family)
    return _match_status_values(status, candidates)


def _match_status_values[S: SyrConnectModelSignature](
    status: object, signatures: list[S]
) -> S | None:
    """Return the first of the signatures that matches the flattened status.

    Detection priority (highest to lowest):
    1. Serial number prefix (srn_prefix):
        If a signature defines 'srn_prefix', and the serial number (getSRN) starts with srn_prefix + srn_infix, this model is selected immediately.
    2. getCNA exact match (cna_equals):
        If a signature defines 'cna_equals' and getCNA matches, this model is selected.
    3. Version prefix/contains:
        If a signature defines 'ver_prefix' or 'ver_contains', and getVER matches, this model is selected.

    Args:
        status: Flattened device status
        signatures: The signatures to choose from

    Returns:
        The matched signature, or None if none matches.
    """
    if not isinstance(status, dict):
        return None

    # Simple normalizations
    cna = str(status.get("getCNA") or "")
    srn = str(status.get("getSRN") or "")
    ver = str(status.get("getVER") or "")

    def srn_match(sig: SyrConnectModelSignature) -> bool:
        return srn.startswith(f"{sig.srn_prefix}{sig.srn_infix}")

    def ver_match(sig: SyrConnectModelSignature) -> bool:
        ver_prefix = sig.ver_prefix
        ver_contains = sig.ver_contains
        if ver_prefix and not ver.startswith(ver_prefix):
            return False
        if ver_contains and ver_contains not in ver:
            return False
        return True

    # Step 1: Check all serial number prefix matches first (highest priority)
    # If a model signature defines 'srn_prefix' and the serial number matches,
    # return this model immediately. This ensures serial number detection always wins over other methods.
    for sig in signatures:
        if sig.srn_prefix and srn_match(sig):
            _LOGGER.debug("Matched signature %s (srn_prefix)", sig.name)
            return sig

    # Step 2: Check all getCNA (model name) exact matches
    # If a model signature defines 'cna_equals' and getCNA matches, return this model.
    for sig in signatures:
        if sig.cna_equals and cna == sig.cna_equals:
            _LOGGER.debug("Matched signature %s (cna_equals)", sig.name)
            return sig

    # Step 3: Check version matches
    # If version prefix or contains is specified and matches, return this model.
    for sig in signatures:
        if (sig.ver_prefix or sig.ver_contains) and ver_match(sig):
            _LOGGER.debug("Matched signature %s (ver)", sig.name)
            return sig

    _LOGGER.debug("No signature matches; keys found: %s", sorted(status)[:20])
    return None
