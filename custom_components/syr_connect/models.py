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
    "display_name": "Unknown model",
    "manufacturer": "Unknown",
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
# - `manufacturer`:                 name of the device manufacturer
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
#
MODEL_SIGNATURES: list[dict[str, Any]] = [
    {
        "base_path": "/pontos-base",
        "display_name": "Pontos Base",
        "manufacturer": "Hansgrohe",
        "name": "pontosbase",
        "ver_prefix": "PontosBase",
    },
    {
        "base_path": None,
        "cna_equals": "LEXplus10",
        "display_name": "LEX Plus 10 Connect",
        "manufacturer": "SYR",
        "name": "lexplus10",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "LEXplus10S",
        "display_name": "LEX Plus 10 S Connect",
        "manufacturer": "SYR",
        "name": "lexplus10s",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "LEXplus10SL",
        "display_name": "LEX Plus 10 SL Connect",
        "manufacturer": "SYR",
        "name": "lexplus10sl",
        "ver_prefix": None,
    },
    {
        "base_path": "/neosoft",
        "display_name": "NeoSoft 2500 Connect",
        "manufacturer": "SYR",
        "name": "neosoft2500",
        "srn_prefix": "206",
    },
    {
        "base_path": "/neosoft",
        "display_name": "NeoSoft 5000 Connect",
        "manufacturer": "SYR",
        "name": "neosoft5000",
        "ver_prefix": "NSS",
        "v_keys": {"getRE1", "getRE2"},
        "v_keys_required": 2,
    },
    {
        "base_path": "/safe-tec",
        "display_name": "Safe-Tech Connect",
        "manufacturer": "SYR",
        "name": "safetech",
        "ver_prefix": "Safe-Tech V4",
    },
    {
        "base_path": "/trio",
        "display_name": "Safe-Tech Plus Connect",
        "manufacturer": "SYR",
        "name": "safetechplus",
        "srn_prefix": "112",
    },
    {
        "base_path": None,
        "display_name": "Safe-T+ Connect",
        "manufacturer": "SYR",
        "name": "safetplus",
        "ver_prefix": "Safe-T",
    },
    {
        "base_path": "/trio",
        "display_name": "Leak Protection Module A25",
        "manufacturer": "Sanibel",
        "name": "sanibelleakprotect",
        "srn_prefix": "501",
    },
    {
        "base_path": "/neosoft",
        "display_name": "Softwater UNO A25",
        "manufacturer": "Sanibel",
        "name": "sanibelsoftwateruno",
        "srn_prefix": "207",
    },
    {
        "base_path": "/trio",
        "display_name": "Trio DFR/LS Connect",
        "manufacturer": "SYR",
        "name": "trio",
        "srn_prefix": "113",
    },
]


def detect_model(flat: dict[str, object]) -> dict[str, Any]:
    """Detect the device model from a flattened attribute dictionary.

    Returns:
        dict: {"name": ..., "display_name": ..., "base_path": ...}
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
        srn_infix = sig.get("srn_infix", "AAA")
        srn_contains = sig.get("srn_contains")
        if not srn_prefix and not srn_contains:
            # Nothing to match against
            return False
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
            _LOGGER.debug("detect_model: detected model %s (srn_equals)", display)
            return {"name": name, "display_name": display, "base_path": base_path, "manufacturer": manufacturer}

    # Step 2: Check all getCNA (model name) exact matches
    # If a model signature defines 'cna_equals' and getCNA matches, return this model.
    for sig in MODEL_SIGNATURES:
        if sig.get("cna_equals") and cna == sig.get("cna_equals"):
            base_path = sig.get("base_path")
            name = sig.get("name")
            display = sig.get("display_name", name)
            manufacturer = sig.get("manufacturer")
            _LOGGER.debug("detect_model: detected model %s (cna_equals)", display)
            return {"name": name, "display_name": display, "base_path": base_path, "manufacturer": manufacturer}

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
            _LOGGER.debug("detect_model: detected model %s (v_keys)", display)
            return {"name": name, "display_name": display, "base_path": base_path, "manufacturer": manufacturer}

        # If only attribute equality is required and already matched, return this model.
        if sig.get("attrs_equals"):
            manufacturer = sig.get("manufacturer")
            _LOGGER.debug("detect_model: detected model %s (attrs_equals)", display)
            return {"name": name, "display_name": display, "base_path": base_path, "manufacturer": manufacturer}

        # If version prefix or contains is specified and matches, return this model.
        if (sig.get("ver_prefix") or sig.get("ver_contains")) and ver_match(sig):
            manufacturer = sig.get("manufacturer")
            _LOGGER.debug("detect_model: detected model %s (ver)", display)
            return {"name": name, "display_name": display, "base_path": base_path, "manufacturer": manufacturer}

    # If no model signature matched, return the unknown model structure.
    _LOGGER.debug("detect_model: unknown model; keys found: %s", sorted(keys)[:20])
    return UNKNOWN_MODEL
