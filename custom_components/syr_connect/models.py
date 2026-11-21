"""Device models of the integration: the signatures of the library with their profiles.

The library (`aiosyrconnect.MODEL_SIGNATURES`) knows how a model is detected,
addressed and named, and the limits of its settings. This module adds what Home
Assistant offers for it, by the model name: the device profile with the entity
allowlists and alarm codes.
"""

from dataclasses import dataclass, fields
import logging

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
    """Device model: the signature of the library and its device profile.

    The fields of `SyrConnectModelSignature` detect, address and name the model; the
    profile adds what Home Assistant offers for it.
    """

    # Profile from a `devices/<name>.py` file with the per-platform entity allowlists
    # and alarm codes of the model (see `helpers.profile.get_model_supported_keys()`). Several
    # models share one profile when they are rebranded variants of the same
    # hardware (e.g. the dk=1500-1506 MultiController family). None means the global
    # allowlists and the generic alarm codes.
    device_profile: SyrConnectDeviceProfile | None = None


# Returned by detect_model when no signature matches or input is invalid.
UNKNOWN_MODEL = SyrConnectModel(
    base_path=None,
    display_name="Unknown model",
    dk=None,
    dkv=None,
    manufacturer="Unknown",
    name="unknown",
)

# Device profile of every signature of the library, by the model name; None for a
# model without a profile. Every signature needs an entry (a missing one fails at
# import); tests/test_models.py checks that there is none without a signature.
_SYR_CONNECT_MODEL_PROFILES: dict[str, SyrConnectDeviceProfile | None] = {
    # ── Safe-T+ (dk=1) ──────────────────────────────────────────────────────────
    "safetplus": safetplus.PROFILE,
    # ── Safe-T Master / Slave / Communication module (dk=2, 3, 5) ──────────────────
    "safetmaster": safetplus.PROFILE,
    "safetslave": safetplus.PROFILE,
    "safetslaveinwall": safetplus.PROFILE,
    "safetcomm": safetplus.PROFILE,
    # ── Safe-T Hygiene module (dk=4) ─────────────────────────────────────────────
    "safethygienemodulecold": safethygienemodule_cold.PROFILE,
    "safethygienemoduleinwall": safethygienemodule.PROFILE,
    "safethygienemodule": safethygienemodule.PROFILE,
    # ── HVA (dk=20) ─────────────────────────────────────────────────────────────
    "hva": hva.PROFILE,
    # ── Inliner-HWA 3300 (dk=25) ─────────────────────────────────────────────────
    "inlinerhwa3300": inlinerhwa.PROFILE,
    # ── i-LEX / LEX (dk=40, dkv=16) ─────────────────────────────────────────────
    "l10": lex.PROFILE,
    "l12": lex.PROFILE,
    "l15": lex.PROFILE,
    "l20": lex.PROFILE,
    "l25": lex.PROFILE,
    "l30": lex.PROFILE,
    "l40": lex.PROFILE,
    "l50": lex.PROFILE,
    "l60": lex.PROFILE,
    "l70": lex.PROFILE,
    "l80": lex.PROFILE,
    "l90": lex.PROFILE,
    "l100": lex.PROFILE,
    "lex10": lex.PROFILE,
    "lex20": lex.PROFILE,
    "lex30": lex.PROFILE,
    "lex40": lex.PROFILE,
    "lex60": lex.PROFILE,
    "lex80": lex.PROFILE,
    "lex100": lex.PROFILE,
    # ── Hygiene module (dk=60-63) ────────────────────────────────────────────────
    "hygienemodulecold": hygienemodule_cold.PROFILE,
    "hygienemodulehot": hygienemodule_hot.PROFILE,
    "hygienemodulehotcold": hygienemodule.PROFILE,
    "hygienemodulecoldhot": hygienemodule.PROFILE,
    # ── LEX Plus 10 (dk=80, dkv=25) ─────────────────────────────────────────────
    "lexplus10": lexplus10s.PROFILE,
    "lexplus10s": lexplus10s.PROFILE,
    "lexplus10sl": lexplus10sl.PROFILE,
    # ── CONTROLICmini (dk=100) ───────────────────────────────────────────────────
    "controlicmini": controlicmini.PROFILE,
    # ── SafeFloor (dk=120/122) ───────────────────────────────────────────────────
    "safefloor": safefloor.PROFILE,
    "safefloorrwc": safefloor.PROFILE,
    "safefloor122": safefloor.PROFILE,
    # ── SafeTech / SafeTech+ (dk=140/141/142/145) ────────────────────────────────
    "safetech": safetech.PROFILE,
    "safetechv3": safetech.PROFILE,
    "safetechv4": safetech.PROFILE,
    "safetechpolygonvatro": safetech.PROFILE,
    "safetechrwc": safetech.PROFILE,
    # Rebranded SafeTech with the same functions.
    "pontosbase": safetech.PROFILE,
    "safetech141": safetech.PROFILE,
    "safetechpluswifi": safetech.PROFILE,
    "safetech145": safetech.PROFILE,
    # ── Specialty devices (dk=160/180/190) ───────────────────────────────────────
    "allinoneplus": allinoneplus.PROFILE,
    "hygbox": hygbox.PROFILE,
    "dosingpump": dosingpump.PROFILE,
    # ── Trio LS platform (dk=1100-1113) ──────────────────────────────────────────
    "triols": trio.PROFILE,
    "concept200replacementfilter": trio.PROFILE,
    "optimatreplacementfilter": trio.PROFILE,
    "safetechplus": safetechplus.PROFILE,
    "trio": trio.PROFILE,
    # ── NeoSoft platform (dk=1200-1222) ──────────────────────────────────────────
    "neosoft5000": neosoft_duo.PROFILE,
    "neosoft2500": neosoft_single.PROFILE,
    "sanibelsoftwateruno": neosoft_single.PROFILE,
    "conceptsingle": neosoft_single.PROFILE,
    "optimasingle": neosoft_single.PROFILE,
    "concept200duo": neosoft_duo.PROFILE,
    "optimat2duo": neosoft_duo.PROFILE,
    "sanibelsoftwaterduo": neosoft_duo.PROFILE,
    "optimaduo": neosoft_duo.PROFILE,
    "conelclearprosofttwin": neosoft_duo.PROFILE,
    "conelclearprosoft": neosoft_single.PROFILE,
    "conceptduo": neosoft_duo.PROFILE,
    "ditechduo": neosoft_duo.PROFILE,
    "takeduo": neosoft_duo.PROFILE,
    "ditechsingle": neosoft_single.PROFILE,
    "takesingle": neosoft_single.PROFILE,
    "neosoftlock2": neosoft_duo.PROFILE,
    "neosoftlock1": neosoft_single.PROFILE,
    # ── MultiController platform (dk=1500-1506) ──────────────────────────────────
    # The role of a MultiController is getDFM: 1 leak protection, 2 connection centre,
    # 3 All-in-One (dkv 500/506 only), 4 automatic backwash, 5 leak protection with
    # backwash filter (dkv 502-506 only). There is deliberately no generic signature for
    # an unknown role: such a device stays an unknown model, so it gets reported
    # instead of silently showing the global allowlists.
    "conelclearproleakprotection": muco_leakprotect.PROFILE,
    "conelclearproconnectioncentre": muco_connectioncentre.PROFILE,
    "conelclearprofill": muco_filling.PROFILE,
    "conelclearprobackwash": muco_backwash.PROFILE,
    "sanibelleakprotect": muco_leakprotect.PROFILE,
    "sanibelconnectioncentre": muco_connectioncentre.PROFILE,
    "sanibelrsa": muco_backwash.PROFILE,
    "ditechleakprotect": muco_leakprotect.PROFILE,
    "ditechconnectioncentre": muco_connectioncentre.PROFILE,
    "ditechbackwash": muco_backwash.PROFILE,
    "ditechbackwashfilter": muco_triolock.PROFILE,
    "takeleakprotect": muco_leakprotect.PROFILE,
    "takeconnectioncentre": muco_connectioncentre.PROFILE,
    "takebackwash": muco_backwash.PROFILE,
    "takebackwashfilter": muco_triolock.PROFILE,
    "conceptleakprotect": muco_leakprotect.PROFILE,
    "conceptconnectioncentre": muco_connectioncentre.PROFILE,
    "conceptbackwash": muco_backwash.PROFILE,
    "concepttriolock": muco_triolock.PROFILE,
    "optimaleakprotect": muco_leakprotect.PROFILE,
    "optimaconnectioncentre": muco_connectioncentre.PROFILE,
    "optimabackwash": muco_backwash.PROFILE,
    "optimatriolock": muco_triolock.PROFILE,
    "syrsafetechlockconnect": muco_leakprotect.PROFILE,
    "syrac3200connect": muco_connectioncentre.PROFILE,
    "syrac3228connect": muco_filling.PROFILE,
    "syrrsaconnect": muco_backwash.PROFILE,
    "syrtriolockconnect": muco_triolock.PROFILE,
}


def _model(signature: SyrConnectModelSignature) -> SyrConnectModel:
    """Return the model of a signature of the library, with its device profile."""
    return SyrConnectModel(
        **{field.name: getattr(signature, field.name) for field in fields(signature)},
        device_profile=_SYR_CONNECT_MODEL_PROFILES[signature.name],
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
