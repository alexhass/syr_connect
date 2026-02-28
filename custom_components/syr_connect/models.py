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
        "device_url": "neosoft",
        "name": "neosoft5000",
        "cna_equals": None,
        "ver_prefix": "NSS",
        "v_keys": {"getRE1", "getRE2"},
        "v_keys_required": 2,
    },
    {
        "display_name": "NeoSoft 2500 Connect",
        "device_url": "neosoft",
        "cna_equals": None,
        "ver_prefix": "NSS",
        "v_keys": {"getRE1"},
        "v_keys_required": 1,
    },
    {
        "display_name": "Trio DFR/LS Connect",
        "device_url": "trio",
        "name": "trio",
        "cna_equals": None,
        "ver_prefix": "syr001",
        "v_keys": {"getAFW", "getVER2"},
        "v_keys_required": 2,
    },
    {
        "display_name": "Safe-Tech+ Connect",
        "device_url": "trio",
        "name": "safetech",
        "cna_equals": None,
        "ver_prefix": "Safe-Tech",
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

    # Simple normalizations
    cna = str(flat.get("getCNA") or "")
    ver = str(flat.get("getVER") or "")
    keys = set(flat.keys())
    _LOGGER.debug("detect_model: keys=%s; getCNA=%s; getVER=%s", sorted(keys)[:120], cna, ver)

    def attrs_match(sig: dict) -> bool:
        attrs = sig.get("attrs_equals")
        if not attrs:
            return True
        for k, v in attrs.items():
            if str(flat.get(k, "")) != str(v):
                return False
        return True

    def version_match(sig: dict) -> bool:
        vp = sig.get("ver_prefix")
        vc = sig.get("ver_contains")
        if vp and not ver.startswith(vp):
            return False
        if vc and vc not in ver:
            return False
        return True

    for sig in MODEL_SIGNATURES:
        name = sig.get("name")
        display = sig.get("display_name", name)
        _LOGGER.debug(
            "detect_model: testing signature %s (cna_equals=%s ver_prefix=%s ver_contains=%s v_keys=%s attrs=%s v_keys_required=%s)",
            name,
            sig.get("cna_equals"),
            sig.get("ver_prefix"),
            sig.get("ver_contains"),
            sig.get("v_keys"),
            sig.get("attrs_equals"),
            sig.get("v_keys_required"),
        )

        # 1) explicit CNA match wins immediately
        if sig.get("cna_equals") and cna == sig.get("cna_equals"):
            _LOGGER.debug("detect_model: detected model %s (cna_equals)", display)
            return {"name": name, "display_name": display}

        # 2) attributes must match if provided; if attrs are required and
        # they don't match, this signature is skipped.
        if not attrs_match(sig):
            continue

        # 3) if the signature defines v_keys, require the fingerprint match
        v_keys = set(sig.get("v_keys") or set())
        if v_keys:
            matches = len(v_keys & keys)
            required = int(sig.get("v_keys_required", 1))
            if matches < required:
                _LOGGER.debug("detect_model: signature %s v_keys matched %d < %d", name, matches, required)
                continue
            if not version_match(sig):
                _LOGGER.debug("detect_model: signature %s version constraints not satisfied (ver=%s)", name, ver)
                continue
            _LOGGER.debug("detect_model: detected model %s (v_keys)", display)
            return {"name": name, "display_name": display}

        # 4) no v_keys: if attrs were present and matched, we've already
        # satisfied detection above. Otherwise fall back to version checks.
        if sig.get("attrs_equals"):
            _LOGGER.debug("detect_model: detected model %s (attrs_equals)", display)
            return {"name": name, "display_name": display}

        if (sig.get("ver_prefix") or sig.get("ver_contains")) and version_match(sig):
            _LOGGER.debug("detect_model: detected model %s (ver)", display)
            return {"name": name, "display_name": display}

    _LOGGER.debug("detect_model: unknown model; keys found: %s", sorted(keys)[:20])
    return {"name": "unknown", "display_name": "Unknown model"}
