"""Device models of the integration: the signatures of the library with their details.

The library (`aiosyrconnect.MODEL_SIGNATURES`) knows how a model is detected and
addressed. This module adds what Home Assistant shows and offers for it, by the model
name: the device profile with the entity allowlists and alarm codes, the name and
manufacturer (per cloud service) and the limits of the entities.
"""

from collections.abc import Mapping
from dataclasses import dataclass, fields
import logging
from typing import NotRequired, TypedDict

from .aiosyrconnect import (
    MODEL_SIGNATURES,
    SyrConnectModelSignature,
    detect_model_signature,
)
from .devices import (
    SyrConnectDeviceProfile,
    allinoneplus,
    controlicmini,
    dosingpump,
    hva,
    hygbox,
    hygienemodule,
    hygienemodule_cold,
    hygienemodule_hot,
    inlinerhwa,
    lex,
    lexplus10s,
    lexplus10sl,
    muco_backwash,
    muco_connectioncentre,
    muco_filling,
    muco_leakprotect,
    muco_triolock,
    neosoft_duo,
    neosoft_single,
    safefloor,
    safetech,
    safetechplus,
    safethygienemodule,
    safethygienemodule_cold,
    safetplus,
    trio,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SyrConnectModel(SyrConnectModelSignature):
    """Device model: the signature of the library and what the integration offers for it.

    The fields of `SyrConnectModelSignature` detect and address the model; the fields
    here describe it in Home Assistant.
    """

    # Profile from a `devices/<name>.py` file with the per-platform entity allowlists
    # and alarm codes of the model (see `helpers.profile.get_model_supported_keys()`). Several
    # models share one profile when they are rebranded variants of the same
    # hardware (e.g. the dk=1500-1506 MultiController family). None means the global
    # allowlists and the generic alarm codes.
    device_profile: SyrConnectDeviceProfile | None = None
    # Human-readable model label used for `DeviceInfo.model` and the local model selector
    display_name: str
    # Human-readable name of the device manufacturer
    manufacturer: str
    # Maximum number of days between regenerations; None means no regeneration interval
    maximum_regeneration_interval: int | None = None
    # Maximum salt tank volume for the salt amount select; only set for models whose salt
    # amount can be set
    maximum_salt_volume: int | None = None
    # Per-service branding: cf_bundle_identifier from `_SYR_CONNECT_API_SERVICES` ->
    # (manufacturer, display name). Used when the same dk/dkv hardware is sold under
    # different names by different vendors; detection and profile stay the same.
    service_branding: Mapping[str, tuple[str, str]] | None = None

    def branded(self, service: str | None) -> tuple[str, str]:
        """Return the manufacturer and display name of the model for a cloud service.

        Args:
            service: The cf_bundle_identifier of the config entry, or None for the
                local JSON API

        Returns:
            The (manufacturer, display_name) pair from `service_branding`, or the
            default one if the service has no branding of its own
        """
        if service is not None and self.service_branding is not None:
            branding = self.service_branding.get(service)
            if branding is not None:
                return branding
        return self.manufacturer, self.display_name


class _SyrConnectModelDetails(TypedDict):
    """The fields of `SyrConnectModel` that the integration adds to a signature."""

    device_profile: NotRequired[SyrConnectDeviceProfile]
    display_name: str
    manufacturer: str
    maximum_regeneration_interval: NotRequired[int]
    maximum_salt_volume: NotRequired[int]
    service_branding: NotRequired[Mapping[str, tuple[str, str]]]


# Returned by detect_model when no signature matches or input is invalid.
UNKNOWN_MODEL = SyrConnectModel(
    base_path=None,
    display_name="Unknown model",
    dk=None,
    dkv=None,
    manufacturer="Unknown",
    name="unknown",
)

# Details of every signature of the library, by the model name. Every signature needs
# an entry (a missing one fails at import); tests/test_models.py checks that there is
# none without a signature.
_SYR_CONNECT_MODEL_DETAILS: dict[str, _SyrConnectModelDetails] = {
    # ── Safe-T+ (dk=1) ──────────────────────────────────────────────────────────
    "safetplus": {
        "device_profile": safetplus.PROFILE,
        "display_name": "Safe-T+ Connect",
        "manufacturer": "SYR",
    },
    # ── Safe-T Master / Slave / Communication module (dk=2, 3, 5) ──────────────────
    "safetmaster": {
        "device_profile": safetplus.PROFILE,
        "display_name": "Safe-T Master",
        "manufacturer": "SYR",
    },
    "safetslave": {
        "device_profile": safetplus.PROFILE,
        "display_name": "Safe-T Slave",
        "manufacturer": "SYR",
    },
    "safetslaveinwall": {
        "device_profile": safetplus.PROFILE,
        "display_name": "Safe-T Slave",
        "manufacturer": "SYR",
    },
    "safetcomm": {
        "device_profile": safetplus.PROFILE,
        "display_name": "Safe-T Communication Module",
        "manufacturer": "SYR",
    },
    # ── Safe-T Hygiene module (dk=4) ─────────────────────────────────────────────
    "safethygienemodulecold": {
        "device_profile": safethygienemodule_cold.PROFILE,
        "display_name": "Safe-T Hygiene Module",
        "manufacturer": "SYR",
    },
    "safethygienemoduleinwall": {
        "device_profile": safethygienemodule.PROFILE,
        "display_name": "Safe-T Hygiene Module",
        "manufacturer": "SYR",
    },
    "safethygienemodule": {
        "device_profile": safethygienemodule.PROFILE,
        "display_name": "Safe-T Hygiene Module",
        "manufacturer": "SYR",
    },
    # ── HVA (dk=20) ─────────────────────────────────────────────────────────────
    "hva": {
        "device_profile": hva.PROFILE,
        "display_name": "HVA",
        "manufacturer": "SYR",
    },
    # ── Inliner-HWA 3300 (dk=25) ─────────────────────────────────────────────────
    "inlinerhwa3300": {
        "device_profile": inlinerhwa.PROFILE,
        "display_name": "Inliner-HWA 3300",
        "manufacturer": "SYR",
    },
    # ── i-LEX / LEX (dk=40, dkv=16) ─────────────────────────────────────────────
    "l10": {
        "device_profile": lex.PROFILE,
        "display_name": "i-LEX 10 Connect",
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 25,
    },
    "l12": {
        "device_profile": lex.PROFILE,
        "display_name": "i-LEX 12 Connect",
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 25,
    },
    "l15": {
        "device_profile": lex.PROFILE,
        "display_name": "i-LEX 15 Connect",
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 25,
    },
    "l20": {
        "device_profile": lex.PROFILE,
        "display_name": "i-LEX 20 Connect",
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 70,
    },
    "l25": {
        "device_profile": lex.PROFILE,
        "display_name": "i-LEX 25 Connect",
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 70,
    },
    "l30": {
        "device_profile": lex.PROFILE,
        "display_name": "i-LEX 30 Connect",
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 70,
    },
    "l40": {
        "device_profile": lex.PROFILE,
        "display_name": "i-LEX 40 Connect",
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 75,
    },
    "l50": {
        "device_profile": lex.PROFILE,
        "display_name": "i-LEX 50 Connect",
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 75,
    },
    "l60": {
        "device_profile": lex.PROFILE,
        "display_name": "i-LEX 60 Connect",
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 110,
    },
    "l70": {
        "device_profile": lex.PROFILE,
        "display_name": "i-LEX 70 Connect",
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 110,
    },
    "l80": {
        "device_profile": lex.PROFILE,
        "display_name": "i-LEX 80 Connect",
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 200,
    },
    "l90": {
        "device_profile": lex.PROFILE,
        "display_name": "i-LEX 90 Connect",
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 200,
    },
    "l100": {
        "device_profile": lex.PROFILE,
        "display_name": "i-LEX 100 Connect",
        "manufacturer": "SYR Oceanic",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 300,
    },
    "lex10": {
        "device_profile": lex.PROFILE,
        "display_name": "LEX 10 Connect",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 25,
    },
    "lex20": {
        "device_profile": lex.PROFILE,
        "display_name": "LEX 20 Connect",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 70,
    },
    "lex30": {
        "device_profile": lex.PROFILE,
        "display_name": "LEX 30 Connect",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 70,
    },
    "lex40": {
        "device_profile": lex.PROFILE,
        "display_name": "LEX 40 Connect",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 75,
    },
    "lex60": {
        "device_profile": lex.PROFILE,
        "display_name": "LEX 60 Connect",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 110,
    },
    "lex80": {
        "device_profile": lex.PROFILE,
        "display_name": "LEX 80 Connect",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 200,
    },
    "lex100": {
        "device_profile": lex.PROFILE,
        "display_name": "LEX 100 Connect",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 99,
        "maximum_salt_volume": 300,
    },
    # ── Hygiene module (dk=60-63) ────────────────────────────────────────────────
    "hygienemodulecold": {
        "device_profile": hygienemodule_cold.PROFILE,
        "display_name": "Hygiene Module (cold)",
        "manufacturer": "SYR",
    },
    "hygienemodulehot": {
        "device_profile": hygienemodule_hot.PROFILE,
        "display_name": "Hygiene Module (hot)",
        "manufacturer": "SYR",
    },
    "hygienemodulehotcold": {
        "device_profile": hygienemodule.PROFILE,
        "display_name": "Hygiene Module (hot and cold)",
        "manufacturer": "SYR",
    },
    "hygienemodulecoldhot": {
        "device_profile": hygienemodule.PROFILE,
        "display_name": "Hygiene Module (cold and hot)",
        "manufacturer": "SYR",
    },
    # ── LEX Plus 10 (dk=80, dkv=25) ─────────────────────────────────────────────
    "lexplus10": {
        "device_profile": lexplus10s.PROFILE,
        "display_name": "LEX Plus 10 Connect",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 4,
        "maximum_salt_volume": 25,
    },
    "lexplus10s": {
        "device_profile": lexplus10s.PROFILE,
        "display_name": "LEX Plus 10 S Connect",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 4,
        "maximum_salt_volume": 25,
    },
    "lexplus10sl": {
        "device_profile": lexplus10sl.PROFILE,
        "display_name": "LEX Plus 10 SL Connect",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 4,
        "maximum_salt_volume": 25,
    },
    # ── CONTROLICmini (dk=100) ───────────────────────────────────────────────────
    "controlicmini": {
        "device_profile": controlicmini.PROFILE,
        "display_name": "CONTROLICmini",
        "manufacturer": "SYR",
    },
    # ── SafeFloor (dk=120/122) ───────────────────────────────────────────────────
    "safefloor": {
        "device_profile": safefloor.PROFILE,
        "display_name": "SafeFloor Connect",
        "manufacturer": "SYR",
        "service_branding": {
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
    },
    "safefloorrwc": {
        "device_profile": safefloor.PROFILE,
        "display_name": "MultiSafe Floor Leak Sensor",
        "manufacturer": "Reliance Valves",
    },
    "safefloor122": {
        "device_profile": safefloor.PROFILE,
        "display_name": "SafeFloor Connect",
        "manufacturer": "SYR",
    },
    # ── SafeTech / SafeTech+ (dk=140/141/142/145) ────────────────────────────────
    "safetech": {
        "device_profile": safetech.PROFILE,
        "display_name": "SafeTech Connect",
        "manufacturer": "SYR",
    },
    "safetechv3": {
        "device_profile": safetech.PROFILE,
        "display_name": "SafeTech V3 Connect",
        "manufacturer": "SYR",
    },
    "safetechv4": {
        "device_profile": safetech.PROFILE,
        "display_name": "SafeTech V4 Connect",
        "manufacturer": "SYR",
    },
    "safetechpolygonvatro": {
        "device_profile": safetech.PROFILE,
        "display_name": "Water Monitor",
        "manufacturer": "POLYGONVATRO",
    },
    "safetechrwc": {
        "device_profile": safetech.PROFILE,
        "display_name": "MultiSafe Leak Detector Control Valve",
        "manufacturer": "Reliance Valves",
    },
    "pontosbase": {
        # Rebranded SafeTech with the same functions.
        "device_profile": safetech.PROFILE,
        "display_name": "Pontos Base",
        "manufacturer": "Hansgrohe",
    },
    "safetech141": {
        "device_profile": safetech.PROFILE,
        "display_name": "SafeTech Connect",
        "manufacturer": "SYR",
    },
    "safetechpluswifi": {
        "device_profile": safetech.PROFILE,
        "display_name": "SafeTech+ Connect",
        "manufacturer": "SYR",
    },
    "safetech145": {
        "device_profile": safetech.PROFILE,
        "display_name": "SafeTech Connect",
        "manufacturer": "SYR",
    },
    # ── Specialty devices (dk=160/180/190) ───────────────────────────────────────
    "allinoneplus": {
        "device_profile": allinoneplus.PROFILE,
        "display_name": "All-in-One+",
        "manufacturer": "SYR",
    },
    "hygbox": {
        "device_profile": hygbox.PROFILE,
        "display_name": "HygBox",
        "manufacturer": "SYR",
        "service_branding": {
            # DT3638 - DITECH Hygienespülbox
            "de.consoft.sanitaerunion.ditech.connect": (
                "DITECH",
                "DITECH Hygiene Flush Box",
            ),
        },
    },
    "dosingpump": {
        "device_profile": dosingpump.PROFILE,
        "display_name": "Dosing Pump",
        "manufacturer": "SYR",
    },
    # ── Trio LS platform (dk=1100-1113) ──────────────────────────────────────────
    "triols": {
        "device_profile": trio.PROFILE,
        "display_name": "Trio LS Connect",
        "manufacturer": "SYR",
    },
    "concept200replacementfilter": {
        "device_profile": trio.PROFILE,
        "display_name": "concept 200 Replacement Filter",
        "manufacturer": "CONCEPT",
    },
    "optimatreplacementfilter": {
        "device_profile": trio.PROFILE,
        "display_name": "Optima T Replacement Filter",
        "manufacturer": "OPTIMA",
    },
    "safetechplus": {
        "device_profile": safetechplus.PROFILE,
        "display_name": "SafeTech Plus Connect",
        "manufacturer": "SYR",
    },
    "trio": {
        "device_profile": trio.PROFILE,
        "display_name": "Trio DFR/LS Connect",
        "manufacturer": "SYR",
    },
    # ── NeoSoft platform (dk=1200-1222) ──────────────────────────────────────────
    "neosoft5000": {
        "device_profile": neosoft_duo.PROFILE,
        "display_name": "NeoSoft 5000 Connect",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 3,
    },
    "neosoft2500": {
        "device_profile": neosoft_single.PROFILE,
        "display_name": "NeoSoft 2500 Connect",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 3,
    },
    "sanibelsoftwateruno": {
        "device_profile": neosoft_single.PROFILE,
        "display_name": "comfort-Softwater UNO A25",
        "manufacturer": "Sanibel",
        "maximum_regeneration_interval": 3,
    },
    "conceptsingle": {
        "device_profile": neosoft_single.PROFILE,
        "display_name": "concept Single Water Softener",
        "manufacturer": "CONCEPT",
        "maximum_regeneration_interval": 3,
    },
    "optimasingle": {
        "device_profile": neosoft_single.PROFILE,
        "display_name": "Optima Single Water Softener",
        "manufacturer": "OPTIMA",
        "maximum_regeneration_interval": 3,
    },
    "concept200duo": {
        "device_profile": neosoft_duo.PROFILE,
        "display_name": "concept 200 Dual Water Softener",
        "manufacturer": "CONCEPT",
        "maximum_regeneration_interval": 3,
    },
    "optimat2duo": {
        "device_profile": neosoft_duo.PROFILE,
        "display_name": "Optima T2 Dual Water Softener",
        "manufacturer": "OPTIMA",
        "maximum_regeneration_interval": 3,
    },
    "sanibelsoftwaterduo": {
        "device_profile": neosoft_duo.PROFILE,
        "display_name": "comfort-Softwater DUO A25",
        "manufacturer": "Sanibel",
        "maximum_regeneration_interval": 3,
    },
    "optimaduo": {
        "device_profile": neosoft_duo.PROFILE,
        "display_name": "Optima Dual Water Softener",
        "manufacturer": "OPTIMA",
        "maximum_regeneration_interval": 3,
    },
    "conelclearprosofttwin": {
        "device_profile": neosoft_duo.PROFILE,
        "display_name": "CLEAR PRO SOFT TWIN",
        "manufacturer": "CONEL",
        "maximum_regeneration_interval": 3,
    },
    "conelclearprosoft": {
        "device_profile": neosoft_single.PROFILE,
        "display_name": "CLEAR PRO SOFT",
        "manufacturer": "CONEL",
        "maximum_regeneration_interval": 3,
    },
    "conceptduo": {
        "device_profile": neosoft_duo.PROFILE,
        "display_name": "concept Dual Water Softener",
        "manufacturer": "CONCEPT",
        "maximum_regeneration_interval": 3,
    },
    "ditechduo": {
        "device_profile": neosoft_duo.PROFILE,
        "display_name": "DITECH Dual Water Softener",
        "manufacturer": "DITECH",
        "maximum_regeneration_interval": 3,
    },
    "takeduo": {
        "device_profile": neosoft_duo.PROFILE,
        "display_name": "TAKE Dual Water Softener",
        "manufacturer": "TAKE",
        "maximum_regeneration_interval": 3,
    },
    "ditechsingle": {
        "device_profile": neosoft_single.PROFILE,
        "display_name": "DITECH Single Water Softener",
        "manufacturer": "DITECH",
        "maximum_regeneration_interval": 3,
    },
    "takesingle": {
        "device_profile": neosoft_single.PROFILE,
        "display_name": "TAKE Single Water Softener",
        "manufacturer": "TAKE",
        "maximum_regeneration_interval": 3,
    },
    "neosoftlock2": {
        "device_profile": neosoft_duo.PROFILE,
        "display_name": "NeoSoft Lock Connect II",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 3,
    },
    "neosoftlock1": {
        "device_profile": neosoft_single.PROFILE,
        "display_name": "NeoSoft Lock Connect I",
        "manufacturer": "SYR",
        "maximum_regeneration_interval": 3,
    },
    # ── MultiController platform (dk=1500-1506) ──────────────────────────────────
    # The role of a MultiController is getDFM: 1 leak protection, 2 connection centre,
    # 3 All-in-One (dkv 500/506 only), 4 automatic backwash, 5 leak protection with
    # backwash filter (dkv 502-506 only). There is deliberately no generic signature for
    # an unknown role: such a device stays an unknown model, so it gets reported
    # instead of silently showing the global allowlists.
    "conelclearproleakprotection": {
        "device_profile": muco_leakprotect.PROFILE,
        "display_name": "CLEAR PRO RETROFIT LEAKAGE PROTECTION",
        "manufacturer": "CONEL",
    },
    "conelclearproconnectioncentre": {
        "device_profile": muco_connectioncentre.PROFILE,
        "display_name": "CLEAR PRO FILL",
        "manufacturer": "CONEL",
    },
    "conelclearprofill": {
        "device_profile": muco_filling.PROFILE,
        "display_name": "CLEAR PRO FILL All-in-One",
        "manufacturer": "CONEL",
    },
    "conelclearprobackwash": {
        "device_profile": muco_backwash.PROFILE,
        "display_name": "CLEAR PRO MULTICONTROL-KIT",
        "manufacturer": "CONEL",
    },
    "sanibelleakprotect": {
        "device_profile": muco_leakprotect.PROFILE,
        "display_name": "comfort-Leak Protection Module A25",
        "manufacturer": "Sanibel",
    },
    "sanibelconnectioncentre": {
        "device_profile": muco_connectioncentre.PROFILE,
        "display_name": "comfort-Connection Module Plus Connect",
        "manufacturer": "Sanibel",
    },
    "sanibelrsa": {
        "device_profile": muco_backwash.PROFILE,
        "display_name": "comfort-Automatic Backwash System RSA A25",
        "manufacturer": "Sanibel",
    },
    "ditechleakprotect": {
        "device_profile": muco_leakprotect.PROFILE,
        "display_name": "DITECH Leak Protection",
        "manufacturer": "DITECH",
    },
    "ditechconnectioncentre": {
        "device_profile": muco_connectioncentre.PROFILE,
        "display_name": "DITECH Connection Module Plus",
        "manufacturer": "DITECH",
    },
    "ditechbackwash": {
        "device_profile": muco_backwash.PROFILE,
        "display_name": "DITECH Automatic Backwash HWS/RF",
        "manufacturer": "DITECH",
    },
    "ditechbackwashfilter": {
        "device_profile": muco_triolock.PROFILE,
        "display_name": "DITECH Backwash Filter Protect",
        "manufacturer": "DITECH",
    },
    "takeleakprotect": {
        "device_profile": muco_leakprotect.PROFILE,
        "display_name": "Leak Protection",
        "manufacturer": "TAKE",
    },
    "takeconnectioncentre": {
        "device_profile": muco_connectioncentre.PROFILE,
        "display_name": "Connection Module Plus",
        "manufacturer": "TAKE",
    },
    "takebackwash": {
        "device_profile": muco_backwash.PROFILE,
        "display_name": "Automatic Backwash for HWS/RF",
        "manufacturer": "TAKE",
    },
    "takebackwashfilter": {
        "device_profile": muco_triolock.PROFILE,
        "display_name": "Backwash Filter with Pressure Reducer and Leak Protection",
        "manufacturer": "TAKE",
    },
    "conceptleakprotect": {
        "device_profile": muco_leakprotect.PROFILE,
        "display_name": "concept 300 Leak Protection",
        "manufacturer": "CONCEPT",
    },
    "conceptconnectioncentre": {
        "device_profile": muco_connectioncentre.PROFILE,
        "display_name": "concept 300 Connection Module Plus",
        "manufacturer": "CONCEPT",
    },
    "conceptbackwash": {
        "device_profile": muco_backwash.PROFILE,
        "display_name": "concept 300 Automatic Backwash RSA",
        "manufacturer": "CONCEPT",
    },
    "concepttriolock": {
        "device_profile": muco_triolock.PROFILE,
        "display_name": "concept 300 Trio Filter with Leak Protection",
        "manufacturer": "CONCEPT",
    },
    "optimaleakprotect": {
        "device_profile": muco_leakprotect.PROFILE,
        "display_name": "Optima T2 Leak Protection",
        "manufacturer": "OPTIMA",
    },
    "optimaconnectioncentre": {
        "device_profile": muco_connectioncentre.PROFILE,
        "display_name": "Optima T2 Connection Module Plus",
        "manufacturer": "OPTIMA",
    },
    "optimabackwash": {
        "device_profile": muco_backwash.PROFILE,
        "display_name": "Optima T2 Automatic Backwash RSA",
        "manufacturer": "OPTIMA",
    },
    "optimatriolock": {
        "device_profile": muco_triolock.PROFILE,
        "display_name": "Optima T2 Leak Protection and Backwash Filter TRIO",
        "manufacturer": "OPTIMA",
    },
    "syrsafetechlockconnect": {
        "device_profile": muco_leakprotect.PROFILE,
        "display_name": "SafeTech Lock Connect",
        "manufacturer": "SYR",
    },
    "syrac3200connect": {
        "device_profile": muco_connectioncentre.PROFILE,
        "display_name": "AC 3200 Connect",
        "manufacturer": "SYR",
    },
    "syrac3228connect": {
        "device_profile": muco_filling.PROFILE,
        "display_name": "AC All-in-One 3228 Connect",
        "manufacturer": "SYR",
    },
    "syrrsaconnect": {
        "device_profile": muco_backwash.PROFILE,
        "display_name": "RSA Connect",
        "manufacturer": "SYR",
    },
    "syrtriolockconnect": {
        "device_profile": muco_triolock.PROFILE,
        "display_name": "TRIO Lock Connect",
        "manufacturer": "SYR",
    },
}


def _model(signature: SyrConnectModelSignature) -> SyrConnectModel:
    """Return the model of a signature of the library, with its details."""
    return SyrConnectModel(
        **{field.name: getattr(signature, field.name) for field in fields(signature)},
        **_SYR_CONNECT_MODEL_DETAILS[signature.name],
    )


# The models, in the order of the signatures of the library: the status checks of the
# detection return the first one that matches.
MODELS: list[SyrConnectModel] = [_model(signature) for signature in MODEL_SIGNATURES]


def detect_model(
    flat: object,
    dk: int | None = None,
    dkv: int | None = None,
    sbt: int | None = None,
    service: str | None = None,
    model: str | None = None,
) -> SyrConnectModel:
    """Detect the device model from the cloud device kind and the flattened status.

    A model chosen at setup is the result without detection: the local JSON API
    reports no device kind, and its status does not tell the models apart. Otherwise
    the library detects it (see `aiosyrconnect.detect_model_signature()`).

    Args:
        flat: Flattened device status
        dk: Cloud API deviceKind, None if unknown
        dkv: Cloud API deviceKindVersion, None if unknown
        sbt: Cloud API device subtype, None if unknown
        service: The cf_bundle_identifier of the config entry, None for the local
            JSON API; the log names the model as this service brands it
        model: The name of the model chosen at setup (CONF_MODEL), None to detect it

    Returns:
        The chosen or matched MODELS entry, or ``UNKNOWN_MODEL`` if no
        signature matches.
    """
    if model is not None:
        return next(
            (sig for sig in MODELS if sig.name == model),
            UNKNOWN_MODEL,
        )
    detected = detect_model_signature(flat, MODELS, dk=dk, dkv=dkv, sbt=sbt)
    if detected is None:
        return UNKNOWN_MODEL
    _LOGGER.debug("detect_model: detected model %s", detected.branded(service)[1])
    return detected
