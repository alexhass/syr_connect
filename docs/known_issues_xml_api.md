# Known issues — SYR XML API

This document lists known deviations between the official SYR Connect XML
API behaviour and what this integration observes in the wild, in the
test fixtures, and in the parsing/encryption layers implemented here.

## Purpose

- Provide a concise, actionable reference of non-conformant XML API
  behaviour the integration must tolerate.
- Point maintainers to the code and tests that implement the necessary
  workarounds.

## Detailed deviations, impacts and references

### 1. Minimal/broken responses are intentionally ignored

- Tentatively be considered a bug on SYR server.
- Description: Some devices (notably Trio DFR/LS series) occasionally
  return responses containing only a tiny set of `c` names
  (`getSRN`, `getALA`, `getNOT`, `getWRN`). These fragments are treated
  as broken and ignored to avoid spurious sensor updates.
- Impact: Partial but valid responses containing only those names will be skipped as a conservative choice to prevent state flapping.
- Mitigation in this project:
  - Ignores broken responses: `_ignore_broken_response()` in `custom_components/syr_connect/response_parser.py` implements this heuristic.

### 2. Offline devices return incorrect data types

- Tentatively be considered part of the design, but it is not ideal.
- Description: API may return incorrect data types if device is offline.
- Impact: Valid responses containing correct setting values, but all device measurements return empty strings and not the last known state. Causing unexpected data type errors in Python.
- Mitigation in this project: Check for sta="3" ("offline" status) and set all values as unknown.

## References

- Parser: [custom_components/syr_connect/response_parser.py](custom_components/syr_connect/response_parser.py)
