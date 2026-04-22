# Known issues — SYR XML API

This document lists known deviations between the official SYR Connect XML
API behaviour and what this integration observes in the wild, in the
test fixtures, and in the parsing/encryption layers implemented here.

Purpose

- Provide a concise, actionable reference of non-conformant XML API
  behaviour the integration must tolerate.
- Point maintainers to the code and tests that implement the necessary
  workarounds.

Detailed deviations, impacts and references

**1. Minimal/broken responses are intentionally ignored**

- Description: Some devices (notably Trio DFR/LS series) occasionally
  return responses containing only a tiny set of `c` names
  (`getSRN`, `getALA`, `getNOT`, `getWRN`). These fragments are treated
  as broken and ignored to avoid spurious sensor updates.
- Impact: Partial but valid responses containing only those names will
  be skipped as a conservative choice to prevent state flapping.
- Project mitigation: `_ignore_broken_response()` in
  `custom_components/syr_connect/response_parser.py` implements this
  heuristic.

References

- Parser: [custom_components/syr_connect/response_parser.py](custom_components/syr_connect/response_parser.py)
