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
        "name": "lexplus10s",
        "cna_equals": "LEXplus10S",
        "ver_prefix": None,
        "threshold": 1,
    },
    {
        "name": "lexplus10sl",
        "cna_equals": "LEXplus10SL",
        "threshold": 1,
    },
    {
        "name": "neosoft",
        "cna_equals": None,
        "ver_prefix": "NSS",
        "threshold": 1,
    },
    {
        "name": "trio",
        "cna_equals": None,
        "ver_prefix": None,
        "ver_contains": "176",
        "attrs_equals": {"getVER2": "176"},
        "threshold": 2,
    },
    {
        "name": "safetplus",
        "cna_equals": None,
        "ver_contains": "Safe-T",
        "threshold": 1,
    },
]


def detect_model(flat: dict[str, object]) -> str | None:
    """Return a detected model name or None.

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

    # If `getCNA` is present, treat it as a unique model identifier.
    if cna.strip():
        return cna.strip()

    for sig in MODEL_SIGNATURES:
        # 1) explicit CNA
        if sig.get("cna_equals") and cna == sig["cna_equals"]:
            return sig["name"]

        # 2) version based
        if sig.get("ver_prefix") and ver.startswith(sig["ver_prefix"]):
            return sig["name"]
        if sig.get("ver_contains") and sig["ver_contains"] in ver:
            return sig["name"]

        # 2b) explicit attribute equality checks
        attrs = sig.get("attrs_equals")
        if attrs and isinstance(attrs, dict):
            matched = True
            for k, v in attrs.items():
                if str(flat.get(k, "")) != str(v):
                    matched = False
                    break
            if matched:
                return sig["name"]

        # 3) fingerprint keys
        allowed = sig.get("v_keys", set())
        if allowed:
            matches = len(keys & allowed)
            if matches >= sig.get("threshold", 1):
                return sig["name"]

    _LOGGER.debug("Unknown device model; sample keys: %s", sorted(keys)[:20])
    return None
