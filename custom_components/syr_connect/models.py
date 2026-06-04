"""Device model detection based on flattened response attributes.

This module provides a small heuristic to identify device models from
the flattened attribute dictionary produced by `ResponseParser._flatten_attributes`.
"""
from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


# Returned by detect_model when no signature matches or input is invalid.
UNKNOWN_MODEL: dict[str, Any] = {
    "base_path": None,
    "configuration_url": "https://syrconnect.de/",
    "display_name": "Unknown model",
    "manufacturer": "Unknown",
    "maximum_regeneration_interval": None,
    "maximum_salt_volume": None,
    "name": "unknown",
}

# Simple model signatures derived from fixtures. Each signature may include
# explicit checks (exact `getCNA` value or version patterns) and a set of
# fingerprint keys where a threshold of matches is required.
#
# Signature fields summary:
# - `attrs_equals`:                 dict of `getX` -> value pairs that must all match
# - `base_path`:                    json api local access base path for the model or None if not applicable
# - `cna_equals`:                   exact match against `getCNA` value (if present)
# - `dk`:                           cloud API deviceKind – the integer `dk` attribute in GetProjectDeviceCollections XML
# - `dkv`:                          cloud API deviceKindVersion – the integer `dkv` attribute in GetProjectDeviceCollections XML;
#                                   for Azure-connected devices this also equals the numeric SRN prefix of newer production units.
# - `manufacturer`:                 name of the device manufacturer
# - `sbt`:                          cloud API device subtype – the integer `sbt` attribute in GetProjectDeviceCollections XML;
#                                   only set when the subtype uniquely identifies this model within its dk/dkv family.
# - `srn_prefix`:                   prefix that `getSRN` must start with
# - `srn_infix`:                    string that must immediately follow `srn_prefix`
#                                   (default: "AAA" – the factory batch code used by all
#                                   current SYR/Hansgrohe/Sanibel devices; override if a
#                                   future production run changes the pattern)
# - `ver_prefix` / `ver_contains`:  require `getVER` to match the prefix or contain
# - `v_keys`:                       set of `getX` keys used as a fingerprint for the model
# - `v_keys_required`:              the minimum number of keys from `v_keys` that must be
#                                   present in the flattened response for the signature to match. When
#                                   `v_keys` are defined, the code also enforces any `ver_*` or
#                                   `attrs_equals` constraints before returning a match.
# - `alarm_clear_via_set`:          if True, the alarm/error state is cleared by sending a setter
#                                   command (setALM) rather than by a clrALM command.
#
MODEL_SIGNATURES: list[dict[str, Any]] = [
    # ── Safe-T+ (dk=1) ──────────────────────────────────────────────────────────
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Safe-T+ Connect",
        "dk": 1,
        "dkv": 6,
        "manufacturer": "SYR",
        "name": "safetplus",
        "ver_prefix": "Safe-T+",
    },

    # ── Safe-T Master / Slave / Communication module (dk=2..5) ─────────────────────
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Safe-T Master",
        "dk": 2,
        "dkv": 2,
        "manufacturer": "SYR",
        "name": "safetmaster",
        # TODO: Untested model.
    },
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Safe-T Slave",
        "dk": 3,
        "dkv": 3,
        "manufacturer": "SYR",
        "name": "safetslave",
        # TODO: Untested model.
    },
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Safe-T Slave",
        "dk": 4,
        "dkv": 4,
        "manufacturer": "SYR",
        "name": "safetslaveinwall",
        # TODO: Untested model.
    },
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Safe-T Communication Module",
        "dk": 5,
        "dkv": 12,
        "manufacturer": "SYR",
        "name": "safetcomm",
        # TODO: Untested model.
    },

    # ── HVA (dk=20) ─────────────────────────────────────────────────────────────
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "HVA",
        "dk": 20,
        "dkv": 19,
        "manufacturer": "SYR",
        "name": "hva",
        # TODO: Untested model.
    },

    # ── Inliner-HWA 3300 (dk=25) ─────────────────────────────────────────────────
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Inliner-HWA 3300",
        "dk": 25,
        "dkv": 26,
        "manufacturer": "SYR",
        "name": "inlinerhwa3300",
        # TODO: Untested model.
    },

    # ── i-LEX / LEX (dk=40, dkv=16) ─────────────────────────────────────────────
    {
        "base_path": None,
        "cna_equals": "L10",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "i-LEX 10 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 25,
        "name": "l10",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "L12",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "i-LEX 12 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 25,
        "name": "l12",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "L15",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "i-LEX 15 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 25,
        "name": "l15",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "L20",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "i-LEX 20 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 70,
        "name": "l20",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "L25",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "i-LEX 25 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 70,
        "name": "l25",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "L30",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "i-LEX 30 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 70,
        "name": "l30",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "L40",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "i-LEX 40 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 75,
        "name": "l40",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "L50",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "i-LEX 50 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 75,
        "name": "l50",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "L60",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "i-LEX 60 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 110,
        "name": "l60",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "L70",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "i-LEX 70 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 110,
        "name": "l70",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "L80",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "i-LEX 80 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 200,
        "name": "l80",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "L90",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "i-LEX 90 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 200,
        "name": "l90",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "L100",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "i-LEX 100 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 300,
        "name": "l100",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "LEX10",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "LEX 10 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 25,
        "name": "lex10",
        "sbt": 1,
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "LEX20",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "LEX 20 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 70,
        "name": "lex20",
        "sbt": 2,
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "LEX30",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "LEX 30 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 70,
        "name": "lex30",
        "sbt": 3,
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "LEX40",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "LEX 40 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 75,
        "name": "lex40",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "LEX60",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "LEX 60 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 110,
        "name": "lex60",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "LEX80",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "LEX 80 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 200,
        "name": "lex80",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "LEX100",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "LEX 100 Connect",
        "dk": 40,
        "dkv": 16,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 300,
        "name": "lex100",
        "ver_prefix": None,
    },

    # ── Hygiene module (dk=60–63) ────────────────────────────────────────────────
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Hygiene Module (cold)",
        "dk": 60,
        "dkv": 21,
        "manufacturer": "SYR",
        "name": "hygienemodulecold",
        # TODO: Untested model.
    },
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Hygiene Module (warm)",
        "dk": 61,
        "dkv": 22,
        "manufacturer": "SYR",
        "name": "hygienemodulwarm",
        # TODO: Untested model.
    },
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Hygiene Module (warm and cold)",
        "dk": 62,
        "dkv": 23,
        "manufacturer": "SYR",
        "name": "hygienemodulwarmcold",
        # TODO: Untested model.
    },
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Hygiene Module (cold and warm)",
        "dk": 63,
        "dkv": 24,
        "manufacturer": "SYR",
        "name": "hygienemodulcoldwarm",
        # TODO: Untested model.
    },

    # ── LEX Plus 10 (dk=80, dkv=25) ─────────────────────────────────────────────
    {
        "base_path": None,
        "cna_equals": "LEXplus10",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "LEX Plus 10 Connect",
        "dk": 80,
        "dkv": 25,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 4,
        "maximum_salt_volume": 25,
        "name": "lexplus10",
        "sbt": 1,
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "LEXplus10S",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "LEX Plus 10 S Connect",
        "dk": 80,
        "dkv": 25,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 4,
        "maximum_salt_volume": 25,
        "name": "lexplus10s",
        "sbt": 2,
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "LEXplus10SL",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "LEX Plus 10 SL Connect",
        "dk": 80,
        "dkv": 25,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 4,
        "maximum_salt_volume": 25,
        "name": "lexplus10sl",
        "sbt": 7,
        "ver_prefix": None,
    },

    # ── CONTROLICmini (dk=100) ───────────────────────────────────────────────────
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "CONTROLICmini",
        "dk": 100,
        "dkv": 27,
        "manufacturer": "SYR",
        "name": "controlicmini",
        # TODO: Untested model.
    },

    # ── SafeFloor (dk=120/122) ───────────────────────────────────────────────────
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "SafeFloor Connect",
        "dk": 120,
        "dkv": 34,
        "manufacturer": "SYR",
        "name": "safefloor",
        "ver_contains": "Floorsensor",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "configuration_url": "https://rwcmultisafe.com/",
        "display_name": "MultiSafe Floor Leak Sensor",
        "dk": 120,
        "dkv": 43,
        "manufacturer": "Reliance Valves",
        "name": "safefloorrwc",
        # TODO: Untested model.
        "srn_prefix": "43",
    },
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "SafeFloor Connect",
        "dk": 122,
        "dkv": 34,
        "manufacturer": "SYR",
        "name": "safefloor122",
        # TODO: Untested model.
    },

    # ── SafeTech / SafeTech+ (dk=140/141/142/145) ────────────────────────────────
    {
        "base_path": "/trio",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "SafeTech Connect",
        "dk": 140,
        "dkv": 35,
        "manufacturer": "SYR",
        "name": "safetech",
        # TODO: Untested model.
        "srn_infix": "aBC",
        "srn_prefix": "123",
    },
    {
        "base_path": "/safe-tec",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "SafeTech V4 Connect",
        "dk": 140,
        "dkv": 35,
        "manufacturer": "SYR",
        "name": "safetechv4",
        "ver_prefix": "Safe-Tech V4",
    },
    {
        "base_path": "/safe-tec",
        "configuration_url": "https://polygonvatro-connect.de/",
        "display_name": "SafeTech Connect",
        "dk": 140,
        "dkv": 38,
        "manufacturer": "POLYGONVATRO",
        "name": "safetechpolygonvatro",
        # TODO: Untested model.
        "srn_prefix": "38",
    },
    {
        "base_path": "/safe-tec",
        "configuration_url": "https://rwcmultisafe.com/",
        "display_name": "MultiSafe Leak Detector Control Valve",
        "dk": 140,
        "dkv": 42,
        "manufacturer": "Reliance Valves",
        "name": "safetechrwc",
        # TODO: Untested model.
        "srn_prefix": "42",
    },
    {
        "base_path": "/pontos-base",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Pontos Base",
        "dk": 140,
        "dkv": None,
        "manufacturer": "Hansgrohe",
        "name": "pontosbase",
        "ver_prefix": "PontosBase",
    },
    {
        "base_path": "/safe-tec",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "SafeTech Connect",
        "dk": 141,
        "dkv": 35,
        "manufacturer": "SYR",
        "name": "safetech141",
        # TODO: Untested model.
    },
    {
        "base_path": None,
        "configuration_url": "https://syrconnect.de/",
        "display_name": "SafeTech+ Connect",
        "dk": 142,
        "dkv": 39,
        "manufacturer": "SYR",
        "name": "safetechpluswifi",
        # TODO: Untested model.
        "srn_prefix": "39",
    },
    {
        "base_path": "/safe-tec",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "SafeTech Connect",
        "dk": 145,
        "dkv": 35,
        "manufacturer": "SYR",
        "name": "safetech145",
        # TODO: Untested model.
    },

    # ── Specialty devices (dk=160/180/190) ───────────────────────────────────────
    {
        "base_path": "/all-in-one",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "All in One +",
        "dk": 160,
        "dkv": 36,
        "manufacturer": "SYR",
        "name": "allinoneplus",
        # TODO: Untested model.
        "srn_prefix": "36",
    },
    {
        "base_path": "/hygbox",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "HygBox",
        "dk": 180,
        "dkv": 37,
        "manufacturer": "SYR",
        "name": "hygbox",
        # TODO: Untested model.
        "srn_prefix": "37",
    },
    {
        "base_path": "/dosing-pump",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Dosing Pump",
        "dk": 190,
        "dkv": 44,
        "manufacturer": "SYR",
        "name": "dosingpump",
        # TODO: Untested model.
        "srn_prefix": "44",
    },

    # ── Trio LS platform (dk=1100–1113) ──────────────────────────────────────────
    {
        "alarm_clear_via_set": True,
        "base_path": "/trio",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Trio LS Connect",
        "dk": 1100,
        "dkv": 100,
        "manufacturer": "SYR",
        "name": "triols",
        # TODO: Untested model.
        "srn_prefix": "100",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/trio",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "concept 200 Replacement Filter",
        "dk": 1110,
        "dkv": 110,
        "manufacturer": "CONCEPT",
        "name": "concept200replacementfilter",
        # TODO: Untested model.
        "srn_prefix": "110",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/trio",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Optima T Replacement Filter",
        "dk": 1111,
        "dkv": 111,
        "manufacturer": "OPTIMA",
        "name": "optimatreplacementfilter",
        # TODO: Untested model.
        "srn_prefix": "111",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/trio",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "SafeTech Plus Connect",
        "dk": 1112,
        "dkv": 112,
        "manufacturer": "SYR",
        "name": "safetechplus",
        "srn_prefix": "112",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/trio",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Trio DFR/LS Connect",
        "dk": 1113,
        "dkv": 113,
        "manufacturer": "SYR",
        "name": "trio",
        "srn_prefix": "113",
    },

    # ── NeoSoft platform (dk=1200–1222) ──────────────────────────────────────────
    {
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "NeoSoft Connect",
        "dk": 1200,
        "dkv": 200,
        "manufacturer": "SYR",
        "name": "neosoft",
        # TODO: Untested model.
        "srn_prefix": "200",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "NeoSoft 2500 Connect",
        "dk": 1206,
        "dkv": 206,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 40,
        "name": "neosoft2500",
        "srn_prefix": "206",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "NeoSoft 5000 Connect",
        "dk": 1206,
        "dkv": 206,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 35,
        "name": "neosoft5000",
        # TODO: Untested model.
        "ver_prefix": "NSS",
        "v_keys": {"getRE1", "getRE2"},
        "v_keys_required": 2,
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Softwater UNO A25",
        "dk": 1207,
        "dkv": 207,
        "manufacturer": "Sanibel",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 35,
        "name": "sanibelsoftwateruno",
        "srn_prefix": "207",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "concept Single Softening System",
        "dk": 1208,
        "dkv": 208,
        "manufacturer": "CONCEPT",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 40,
        "name": "conceptsingle",
        # TODO: Untested model.
        "srn_prefix": "208",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Optima Single Softening System",
        "dk": 1209,
        "dkv": 209,
        "manufacturer": "OPTIMA",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 40,
        "name": "optimasingle",
        # TODO: Untested model.
        "srn_prefix": "209",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "concept 200 Double Softening System",
        "dk": 1210,
        "dkv": 210,
        "manufacturer": "CONCEPT",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 35,
        "name": "concept200duo",
        # TODO: Untested model.
        "srn_prefix": "210",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Optima T2.2 Double Softening System",
        "dk": 1211,
        "dkv": 211,
        "manufacturer": "OPTIMA",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 35,
        "name": "optimat22duo",
        # TODO: Untested model.
        "srn_prefix": "211",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Softwater DUO A25",
        "dk": 1212,
        "dkv": 212,
        "manufacturer": "Sanibel",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 35,
        "name": "sanibelsoftwaterduo",
        # TODO: Untested model.
        "srn_prefix": "212",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Optima Double Softening System",
        "dk": 1213,
        "dkv": 213,
        "manufacturer": "OPTIMA",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 35,
        "name": "optimaduo",
        # TODO: Untested model.
        "srn_prefix": "213",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://conelclearpro.de/",
        "display_name": "CLEAR PRO SOFT TWIN",
        "dk": 1214,
        "dkv": 214,
        "manufacturer": "CONEL",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 35,
        "name": "conelclearprosofttwin",
        "srn_prefix": "214",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://conelclearpro.de/",
        "display_name": "CLEAR PRO SOFT",
        "dk": 1215,
        "dkv": 215,
        "manufacturer": "CONEL",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 40,
        "name": "conelclearprosoft",
        "srn_prefix": "215",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "concept Double Softening System",
        "dk": 1216,
        "dkv": 216,
        "manufacturer": "CONCEPT",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 35,
        "name": "conceptduo",
        # TODO: Untested model.
        "srn_prefix": "216",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Ditech Double Softening System",
        "dk": 1217,
        "dkv": 217,
        "manufacturer": "DITECH",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 35,
        "name": "ditechduo",
        # TODO: Untested model.
        "srn_prefix": "217",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "TAKE Double Softening System",
        "dk": 1218,
        "dkv": 218,
        "manufacturer": "TAKE",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 35,
        "name": "takeduo",
        # TODO: Untested model.
        "srn_prefix": "218",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Ditech Single Softening System",
        "dk": 1219,
        "dkv": 219,
        "manufacturer": "DITECH",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 40,
        "name": "ditechsingle",
        # TODO: Untested model.
        "srn_prefix": "219",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "TAKE Single Softening System",
        "dk": 1220,
        "dkv": 220,
        "manufacturer": "TAKE",
        "maximum_regeneration_interval": 3,
        "maximum_salt_volume": 40,
        "name": "takesingle",
        # TODO: Untested model.
        "srn_prefix": "220",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "NeoSoft Lock Connect II",
        "dk": 1221,
        "dkv": 221,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 3,
        "name": "neosoftlock2",
        # TODO: Untested model.
        "srn_prefix": "221",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/neosoft",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "NeoSoft Lock Connect I",
        "dk": 1222,
        "dkv": 222,
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 3,
        "name": "neosoftlock1",
        # TODO: Untested model.
        "srn_prefix": "222",
    },

    # ── MultiController platform (dk=1500–1506) ──────────────────────────────────
    {
        "alarm_clear_via_set": True,
        "base_path": "/trio",
        "configuration_url": "https://conelclearpro.de/",
        "display_name": "Conel MultiController",
        "dk": 1500,
        "dkv": 500,
        "manufacturer": "CONEL",
        "name": "conelmuco",
        # TODO: Untested model.
        "srn_prefix": "500",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/trio",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Leak Protection Module A25",
        "dk": 1501,
        "dkv": 501,
        "manufacturer": "Sanibel",
        "name": "sanibelleakprotect",
        "srn_prefix": "501",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/trio",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Ditech Multicontroller",
        "dk": 1502,
        "dkv": 502,
        "manufacturer": "DITECH",
        "name": "ditechmuco",
        # TODO: Untested model.
        "srn_prefix": "502",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/trio",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "TAKE Multicontroller",
        "dk": 1503,
        "dkv": 503,
        "manufacturer": "TAKE",
        "name": "takemuco",
        # TODO: Untested model.
        "srn_prefix": "503",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/trio",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "concept Multicontroller",
        "dk": 1504,
        "dkv": 504,
        "manufacturer": "CONCEPT",
        "name": "conceptmuco",
        # TODO: Untested model.
        "srn_prefix": "504",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/trio",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Optima Multicontroller",
        "dk": 1505,
        "dkv": 505,
        "manufacturer": "OPTIMA",
        "name": "optimamuco",
        # TODO: Untested model.
        "srn_prefix": "505",
    },
    {
        "alarm_clear_via_set": True,
        "base_path": "/trio",
        "configuration_url": "https://syrconnect.de/",
        "display_name": "Syr Multicontroller",
        "dk": 1506,
        "dkv": 506,
        "manufacturer": "SYR",
        "name": "syrmuco",
        # TODO: Untested model.
        "srn_prefix": "506",
    },
]


def detect_model(flat: dict[str, object]) -> dict[str, Any]:
    """Detect the device model from a flattened attribute dictionary.

    Returns:
        dict: {"name": ..., "display_name": ..., "base_path": ..., "manufacturer": ..., "configuration_url": ..., "maximum_regeneration_interval": ...}
        If no signature matches, returns an 'unknown' model dict.

    Detection priority (highest to lowest):
    1. Serial number prefix (srn_prefix):
        If a signature defines 'srn_prefix', and the serial number (getSRN) starts with srn_prefix + 'AAA', this model is selected immediately.
    2. Serial number contains (srn_contains):
        If a signature defines 'srn_contains' and it is found in the serial number, this model is selected.
    3. getCNA exact match (cna_equals):
        If a signature defines 'cna_equals' and getCNA matches, this model is selected.
    4. Attribute match (attrs_equals):
        If a signature defines 'attrs_equals' and all specified attributes match, this model is selected.
    5. v_keys fingerprint:
        If a signature defines 'v_keys', at least 'v_keys_required' of those keys must be present in the flattened response. If version or attribute constraints are also specified, they must match as well.
    6. Version prefix/contains:
        If a signature defines 'ver_prefix' or 'ver_contains', and getVER matches, this model is selected.

    If no signature matches, returns the unknown model structure.
    """
    if not isinstance(flat, dict):
        return UNKNOWN_MODEL

    # Simple normalizations
    cna = str(flat.get("getCNA") or "")
    srn = str(flat.get("getSRN") or "")
    ver = str(flat.get("getVER") or "")
    keys = set(flat.keys())

    def attrs_match(sig: dict) -> bool:
        attrs = sig.get("attrs_equals")
        if not attrs:
            return True
        for k, v in attrs.items():
            if str(flat.get(k, "")) != str(v):
                return False
        return True

    def srn_match(sig: dict) -> bool:
        srn_prefix = sig.get("srn_prefix")
        # Default maintains compatibility with existing signatures that only specify srn_prefix without srn_infix.
        # If srn_prefix is defined but srn_infix is not, it will check for srn_prefix followed by 'AAA' as the
        # default infix. This allows existing signatures to continue working without modification while enabling
        # more flexible matching for new signatures that specify a different infix.
        srn_infix = sig.get("srn_infix", "AAA")
        srn_contains = sig.get("srn_contains")
        if srn_prefix and not srn.startswith(f"{srn_prefix}{srn_infix}"):
            return False
        if srn_contains and srn_contains not in srn:
            return False
        return True

    def ver_match(sig: dict) -> bool:
        ver_prefix = sig.get("ver_prefix")
        ver_contains = sig.get("ver_contains")
        if ver_prefix and not ver.startswith(ver_prefix):
            return False
        if ver_contains and ver_contains not in ver:
            return False
        return True

    # Step 1: Check all serial number prefix/contains matches first (highest priority)
    # If a model signature defines 'srn_prefix' or 'srn_contains' and the serial number matches,
    # return this model immediately. This ensures serial number detection always wins over other methods.
    for sig in MODEL_SIGNATURES:
        if (sig.get("srn_prefix") or sig.get("srn_contains")) and srn_match(sig):
            base_path = sig.get("base_path")
            name = sig.get("name")
            display = sig.get("display_name", name)
            manufacturer = sig.get("manufacturer")
            configuration_url = sig.get("configuration_url")
            maximum_regeneration_interval = sig.get("maximum_regeneration_interval")
            maximum_salt_volume = sig.get("maximum_salt_volume")
            _LOGGER.debug("detect_model: detected model %s (srn_equals)", display)
            return {"name": name, "display_name": display, "base_path": base_path, "manufacturer": manufacturer, "configuration_url": configuration_url, "maximum_regeneration_interval": maximum_regeneration_interval, "maximum_salt_volume": maximum_salt_volume}

    # Step 2: Check all getCNA (model name) exact matches
    # If a model signature defines 'cna_equals' and getCNA matches, return this model.
    for sig in MODEL_SIGNATURES:
        if sig.get("cna_equals") and cna == sig.get("cna_equals"):
            base_path = sig.get("base_path")
            name = sig.get("name")
            display = sig.get("display_name", name)
            manufacturer = sig.get("manufacturer")
            configuration_url = sig.get("configuration_url")
            maximum_regeneration_interval = sig.get("maximum_regeneration_interval")
            maximum_salt_volume = sig.get("maximum_salt_volume")
            _LOGGER.debug("detect_model: detected model %s (cna_equals)", display)
            return {"name": name, "display_name": display, "base_path": base_path, "manufacturer": manufacturer, "configuration_url": configuration_url, "maximum_regeneration_interval": maximum_regeneration_interval, "maximum_salt_volume": maximum_salt_volume}

    # Step 3: Check attribute matches, fingerprint keys, and version matches
    # This block handles more complex detection using attribute equality, fingerprint keys, and version info.
    for sig in MODEL_SIGNATURES:
        base_path = sig.get("base_path")
        name = sig.get("name")
        display = sig.get("display_name", name)

        # If the signature requires certain attributes to match, skip if not satisfied.
        if not attrs_match(sig):
            continue

        # If the signature defines fingerprint keys (v_keys), require enough keys to match.
        v_keys = set(sig.get("v_keys") or set())
        if v_keys:
            matches = len(v_keys & keys)
            required = int(sig.get("v_keys_required", 1))
            if matches < required:
                _LOGGER.debug("detect_model: signature %s v_keys matched %d < %d", name, matches, required)
                continue
            # If version constraints are present, require them to match as well.
            if not ver_match(sig):
                _LOGGER.debug("detect_model: signature %s version constraints not satisfied (ver=%s)", name, ver)
                continue
            manufacturer = sig.get("manufacturer")
            configuration_url = sig.get("configuration_url")
            maximum_regeneration_interval = sig.get("maximum_regeneration_interval")
            maximum_salt_volume = sig.get("maximum_salt_volume")
            _LOGGER.debug("detect_model: detected model %s (v_keys)", display)
            return {"name": name, "display_name": display, "base_path": base_path, "manufacturer": manufacturer, "configuration_url": configuration_url, "maximum_regeneration_interval": maximum_regeneration_interval, "maximum_salt_volume": maximum_salt_volume}

        # If only attribute equality is required and already matched, return this model.
        if sig.get("attrs_equals"):
            manufacturer = sig.get("manufacturer")
            configuration_url = sig.get("configuration_url")
            maximum_regeneration_interval = sig.get("maximum_regeneration_interval")
            maximum_salt_volume = sig.get("maximum_salt_volume")
            _LOGGER.debug("detect_model: detected model %s (attrs_equals)", display)
            return {"name": name, "display_name": display, "base_path": base_path, "manufacturer": manufacturer, "configuration_url": configuration_url, "maximum_regeneration_interval": maximum_regeneration_interval, "maximum_salt_volume": maximum_salt_volume}

        # If version prefix or contains is specified and matches, return this model.
        if (sig.get("ver_prefix") or sig.get("ver_contains")) and ver_match(sig):
            manufacturer = sig.get("manufacturer")
            configuration_url = sig.get("configuration_url")
            maximum_regeneration_interval = sig.get("maximum_regeneration_interval")
            maximum_salt_volume = sig.get("maximum_salt_volume")
            _LOGGER.debug("detect_model: detected model %s (ver)", display)
            return {"name": name, "display_name": display, "base_path": base_path, "manufacturer": manufacturer, "configuration_url": configuration_url, "maximum_regeneration_interval": maximum_regeneration_interval, "maximum_salt_volume": maximum_salt_volume}

    # If no model signature matched, return the unknown model structure.
    _LOGGER.debug("detect_model: unknown model; keys found: %s", sorted(keys)[:20])
    return UNKNOWN_MODEL
