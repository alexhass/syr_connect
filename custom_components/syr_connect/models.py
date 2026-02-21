"""Device model detection based on flattened response attributes.

This module provides a small heuristic to identify device models from
the flattened attribute dictionary produced by `ResponseParser._flatten_attributes`.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable

_LOGGER = logging.getLogger(__name__)


# Simple model signatures derived from fixtures. Each signature may include
# explicit checks (exact `getCNA` value or version patterns) and a set of
# fingerprint keys where a threshold of matches is required.
#
# Signature fields summary:
# - `cna_equals`: exact match against `getCNA` value (if present)
# - `ver_prefix` / `ver_contains`: require `getVER` to match the prefix or contain
# - `attrs_equals`: dict of `getX` -> value pairs that must all match
# - `v_keys`: set of `getX` keys used as a fingerprint for the model
# - `v_keys_required`: the minimum number of keys from `v_keys` that must be
#   present in the flattened response for the signature to match. When
#   `v_keys` are defined, the code also enforces any `ver_*` or
#   `attrs_equals` constraints before returning a match.
#
MODEL_SIGNATURES: Iterable[dict] = [
    {
        "display_name": "LEX Plus 10 Connect",
        "name": "lexplus10",
        "cna_equals": "LEXplus10",
        "ver_prefix": None,
    },
    {
        "display_name": "LEX Plus 10 S Connect",
        "name": "lexplus10s",
        "cna_equals": "LEXplus10S",
        "ver_prefix": None,
    },
    {
        "display_name": "LEX Plus 10 SL Connect",
        "name": "lexplus10sl",
        "cna_equals": "LEXplus10SL",
        "ver_prefix": None,
    },
    {
        "display_name": "NeoSoft 5000 Connect",
        "name": "neosoft5000",
        "cna_equals": None,
        "ver_prefix": "NSS",
        "v_keys": {"getRE1", "getRE2"},
        "v_keys_required": 2,
    },
    {
        "display_name": "NeoSoft 2500 Connect",
        "name": "neosoft2500",
        "cna_equals": None,
        "ver_prefix": "NSS",
        "v_keys": {"getRE1"},
        "v_keys_required": 1,
    },
    {
        "display_name": "Trio DFR/LS Connect",
        "name": "trio",
        "cna_equals": None,
        "ver_prefix": None,
        "ver_contains": "176",
        "attrs_equals": {"getVER2": "176"},
    },
    {
        "display_name": "Safe-T+ Connect",
        "name": "safetplus",
        "cna_equals": None,
        "ver_contains": "Safe-T",
    },
]


def detect_model(flat: dict[str, object]) -> dict:
    """Return a detected model as {'name':..., 'display_name':...}.
    If no signature matches, return an 'unknown' model dict.

    The function applies a small set of rules in order:
    1. `getCNA` exact match
      2. If a signature declares `v_keys`, at least `v_keys_required` of those
          keys must be present in the flattened response. If the signature
         also specifies `ver_prefix`/`ver_contains` or `attrs_equals`, those
         are required in addition to the `v_keys` match.
     3. If a signature does not define `v_keys`, fall back to
         `getVER` prefix/contains and `attrs_equals` checks.
    """
    if not isinstance(flat, dict):
        return None

    # Normalize helpers
    cna = str(flat.get("getCNA", "")) if flat.get("getCNA") is not None else ""
    ver = str(flat.get("getVER", "")) if flat.get("getVER") is not None else ""
    keys = set(flat.keys())

    for sig in MODEL_SIGNATURES:
        # 1) explicit CNA
        if sig.get("cna_equals") and cna == sig["cna_equals"]:
            display = sig.get("display_name", sig["name"])
            _LOGGER.debug("Detected device model: %s (cna_equals)", display)
            return {"name": sig["name"], "display_name": display}
        # explicit attribute equality checks
        attrs = sig.get("attrs_equals")
        attrs_matched = False
        if attrs and isinstance(attrs, dict):
            attrs_matched = True
            for k, v in attrs.items():
                if str(flat.get(k, "")) != str(v):
                    attrs_matched = False
                    break
            if not attrs_matched:
                # if attributes are required but don't match, skip this signature
                continue

        # If signature defines v_keys, require fingerprint match first
        v_keys = sig.get("v_keys") or set()
        if v_keys:
            matches = len(keys & set(v_keys))
            if matches < sig.get("v_keys_required", 1):
                continue
            # require version constraints if provided
            if sig.get("ver_prefix") and not ver.startswith(sig["ver_prefix"]):
                continue
            if sig.get("ver_contains") and sig["ver_contains"] not in ver:
                continue
            display = sig.get("display_name", sig["name"])
            _LOGGER.debug("Detected device model: %s (v_keys match=%d)", display, matches)
            return {"name": sig["name"], "display_name": display}
        # If no v_keys required, attributes-only matches should already
        # have returned above. Fall back to version checks.
        if sig.get("ver_prefix") and ver.startswith(sig["ver_prefix"]):
            display = sig.get("display_name", sig["name"])
            _LOGGER.debug("Detected device model: %s (ver_prefix)", display)
            return {"name": sig["name"], "display_name": display}
        if sig.get("ver_contains") and sig["ver_contains"] in ver:
            display = sig.get("display_name", sig["name"])
            _LOGGER.debug("Detected device model: %s (ver_contains)", display)
            return {"name": sig["name"], "display_name": display}

    _LOGGER.debug("Unknown device model; sample keys: %s", sorted(keys)[:20])
    return {"name": "unknown", "display_name": "Unknown model"}
