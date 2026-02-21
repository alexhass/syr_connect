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
MODEL_SIGNATURES: Iterable[dict] = [
    {
        "display_name": "LEX Plus 10 Connect",
        "name": "lexplus10",
        "cna_equals": "LEXplus10",
        "ver_prefix": None,
        "threshold": 1,
    },
    {
        "display_name": "LEX Plus 10 S Connect",
        "name": "lexplus10s",
        "cna_equals": "LEXplus10S",
        "ver_prefix": None,
        "threshold": 1,
    },
    {
        "display_name": "LEX Plus 10 SL Connect",
        "name": "lexplus10sl",
        "cna_equals": "LEXplus10SL",
        "ver_prefix": None,
        "threshold": 1,
    },
    {
        "display_name": "NeoSoft 5000 Connect",
        "name": "neosoft5000",
        "cna_equals": None,
        "ver_prefix": "NSS",
        "v_keys": {"getRE1", "getRE2"},
        "threshold": 2,
    },
    {
        "display_name": "NeoSoft 2500 Connect",
        "name": "neosoft2500",
        "cna_equals": None,
        "ver_prefix": "NSS",
        "v_keys": {"getRE1"},
        "threshold": 1,
    },
    {
        "display_name": "Trio DFR/LS Connect",
        "name": "trio",
        "cna_equals": None,
        "ver_prefix": None,
        "ver_contains": "176",
        "attrs_equals": {"getVER2": "176"},
        "threshold": 2,
    },
    {
        "display_name": "Safe-T+ Connect",
        "name": "safetplus",
        "cna_equals": None,
        "ver_contains": "Safe-T",
        "threshold": 1,
    },
]


def detect_model(flat: dict[str, object]) -> dict:
    """Return a detected model as {'name':..., 'display_name':...}.
    If no signature matches, return an 'unknown' model dict.

    The function applies a small set of rules in order:
    1. `getCNA` exact match
    2. `getVER` prefix/contains rules
    3. fingerprint key intersection with threshold
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

        # 2) version based
        if sig.get("ver_prefix") and ver.startswith(sig["ver_prefix"]):
            display = sig.get("display_name", sig["name"])
            _LOGGER.debug("Detected device model: %s (ver_prefix)", display)
            return {"name": sig["name"], "display_name": display}
        if sig.get("ver_contains") and sig["ver_contains"] in ver:
            display = sig.get("display_name", sig["name"])
            _LOGGER.debug("Detected device model: %s (ver_contains)", display)
            return {"name": sig["name"], "display_name": display}

        # 2b) explicit attribute equality checks
        attrs = sig.get("attrs_equals")
        if attrs and isinstance(attrs, dict):
            matched = True
            for k, v in attrs.items():
                if str(flat.get(k, "")) != str(v):
                    matched = False
                    break
            if matched:
                display = sig.get("display_name", sig["name"])
                _LOGGER.debug("Detected device model: %s (attrs_equals)", display)
                return {"name": sig["name"], "display_name": display}

        # 3) fingerprint keys
        allowed = sig.get("v_keys", set())
        if allowed:
            matches = len(keys & allowed)
            if matches >= sig.get("threshold", 1):
                display = sig.get("display_name", sig["name"])
                _LOGGER.debug("Detected device model: %s (v_keys match=%d)", display, matches)
                return {"name": sig["name"], "display_name": display}

    _LOGGER.debug("Unknown device model; sample keys: %s", sorted(keys)[:20])
    return {"name": "unknown", "display_name": "Unknown model"}
