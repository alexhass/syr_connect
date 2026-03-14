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
# - `attrs_equals`: dict of `getX` -> value pairs that must all match
# - `base_path`: json api local access base path for the model or None if not applicable
# - `cna_equals`: exact match against `getCNA` value (if present)
# - `ver_prefix` / `ver_contains`: require `getVER` to match the prefix or contain
# - `v_keys`: set of `getX` keys used as a fingerprint for the model
# - `v_keys_required`: the minimum number of keys from `v_keys` that must be
#   present in the flattened response for the signature to match. When
#   `v_keys` are defined, the code also enforces any `ver_*` or
#   `attrs_equals` constraints before returning a match.
#
MODEL_SIGNATURES: Iterable[dict] = [
    {
        "base_path": None,
        "display_name": "Sanibel Softwater UNO A25",
        "name": "sanibelneosoft2500",
        "srn_prefix": "207",
    },
    {
        "base_path": None,
        "display_name": "Sanibel Leak protection module A25",
        "name": "sanibelleakprotecta25",
        "srn_prefix": "501",
    },
    {
        "base_path": None,
        "cna_equals": "LEXplus10",
        "display_name": "LEX Plus 10 Connect",
        "name": "lexplus10",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "LEXplus10S",
        "display_name": "LEX Plus 10 S Connect",
        "name": "lexplus10s",
        "ver_prefix": None,
    },
    {
        "base_path": None,
        "cna_equals": "LEXplus10SL",
        "display_name": "LEX Plus 10 SL Connect",
        "name": "lexplus10sl",
        "ver_prefix": None,
    },
    {
        "base_path": "/neosoft",
        "display_name": "NeoSoft 2500 Connect",
        "name": "neosoft2500",
        "srn_prefix": "206",
    },
    {
        "base_path": "/neosoft",
        "display_name": "NeoSoft 5000 Connect",
        "name": "neosoft5000",
        "ver_prefix": "NSS",
        "v_keys": {"getRE1", "getRE2"},
        "v_keys_required": 2,
    },
    {
        "base_path": "/trio",
        "display_name": "Trio DFR/LS Connect",
        "name": "trio",
        "srn_prefix": "113",
    },
    {
        "base_path": "/trio",
        "display_name": "Safe-Tech+ Connect",
        "name": "safetech",
        "ver_prefix": "Safe-Tech",
    },
    {
        "base_path": None,
        "display_name": "Safe-T+ Connect",
        "name": "safetplus",
        "ver_prefix": "Safe-T",
    },
]


def detect_model(flat: dict[str, object]) -> dict:
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
        return None

    # Simple normalizations
    cna = str(flat.get("getCNA") or "")
    srn = str(flat.get("getSRN") or "")
    ver = str(flat.get("getVER") or "")
    keys = set(flat.keys())
    _LOGGER.debug("detect_model: keys=%s; getCNA=%s; getSRN=%s; getVER=%s", sorted(keys)[:120], cna, srn, ver)

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
        srn_contains = sig.get("srn_contains")
        if srn_prefix and not srn.startswith(f"{srn_prefix}AAA"):
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

    for sig in MODEL_SIGNATURES:
        base_path = sig.get("base_path")
        name = sig.get("name")
        display = sig.get("display_name", name)

        _LOGGER.debug(
            "detect_model: testing signature %s (attrs=%s base_path=%s cna_equals=%s srn_prefix=%s srn_contains=%s ver_prefix=%s ver_contains=%s v_keys=%s v_keys_required=%s)",
            name,
            sig.get("attrs_equals"),
            base_path,
            sig.get("cna_equals"),
            sig.get("srn_prefix"),
            sig.get("srn_contains"),
            sig.get("ver_prefix"),
            sig.get("ver_contains"),
            sig.get("v_keys"),
            sig.get("v_keys_required"),
        )

        # 1) Explicit model (getTYP) match from serial number prefix wins immediately.
        if (sig.get("srn_prefix") or sig.get("srn_contains")) and srn_match(sig):
            _LOGGER.debug("detect_model: detected model %s (srn_equals)", display)
            result = {"name": name, "display_name": display, "base_path": base_path}
            return result

        # 2) explicit CNA match wins immediately.
        if sig.get("cna_equals") and cna == sig.get("cna_equals"):
            _LOGGER.debug("detect_model: detected model %s (cna_equals)", display)
            result = {"name": name, "display_name": display, "base_path": base_path}
            return result

        # 3) attributes must match if provided; if attrs are required and
        # they don't match, this signature is skipped.
        if not attrs_match(sig):
            continue

        # 4) if the signature defines v_keys, require the fingerprint match.
        v_keys = set(sig.get("v_keys") or set())
        if v_keys:
            matches = len(v_keys & keys)
            required = int(sig.get("v_keys_required", 1))
            if matches < required:
                _LOGGER.debug("detect_model: signature %s v_keys matched %d < %d", name, matches, required)
                continue
            if not ver_match(sig):
                _LOGGER.debug("detect_model: signature %s version constraints not satisfied (ver=%s)", name, ver)
                continue
            _LOGGER.debug("detect_model: detected model %s (v_keys)", display)
            result = {"name": name, "display_name": display, "base_path": base_path}
            return result

        # 5) no v_keys: if attrs were present and matched, we've already
        # satisfied detection above. Otherwise fall back to version checks.
        if sig.get("attrs_equals"):
            _LOGGER.debug("detect_model: detected model %s (attrs_equals)", display)
            result = {"name": name, "display_name": display, "base_path": base_path}
            return result

        if (sig.get("ver_prefix") or sig.get("ver_contains")) and ver_match(sig):
            _LOGGER.debug("detect_model: detected model %s (ver)", display)
            result = {"name": name, "display_name": display, "base_path": base_path}
            return result

    _LOGGER.debug("detect_model: unknown model; keys found: %s", sorted(keys)[:20])
    return {"name": "unknown", "display_name": "Unknown model", "base_path": None}
