---
description: Per-model device files, model detection and sensor allowlists
applyTo: "custom_components/syr_connect/{devices/*.py,models.py,helpers.py}"
---

# Device files and model detection

- Global allowlists live in `const.py`. A model may override them per platform in `devices/<device_file>.py` with `SENSOR_KNOWN_KEYS`, `SELECT_KNOWN_KEYS`, `SWITCH_KNOWN_KEYS`, `BINARY_SENSOR_KNOWN_KEYS`, `BUTTON_KNOWN_KEYS`, `VALVE_KNOWN_KEYS` and `UPDATE_KNOWN_KEYS`. An override replaces the global set completely.
- Use positive allowlists only. Do not add exclusion lists to `MODEL_SIGNATURES`.
- An override must still contain structurally required keys such as `dst`, otherwise `registry_cleanup()` deletes them.
- An empty override (`set()`) is valid and means "no entities". Always check `is None` when reading an override.
- A key becomes an entity only if it is in both the device file and the global allowlist in `const.py`.
- The official per-model validity matrix in `docs/syrconnect-protocol.md` beats fixture contents. A key that is present in a fixture can still be a stub value. Only judge by fixture for properties the matrix does not cover.
- Fixture co-presence of a key across models does not prove it is generic. When domain knowledge and fixture data conflict, ask the maintainer.
- Match the exact `dk`/`dkv` in `models.py` before mapping a name from the matrix to a device file. Similar names can be different products.
- `device_file` names use underscores (valid module names) and describe the role, for example `muco_filling`. Do not use the raw `getDFM` number, its meaning differs per `dk`/`dkv` family.
- `attrs_equals` in `MODEL_SIGNATURES` is matched against the flattened status (`getXXX` keys only). `dk` and `dkv` are never present there.
- A specific signature needs the same `srn_prefix` as its generic sibling plus its `attrs_equals`, otherwise the generic one always wins.
- Rebrand siblings share one device file (for example all NeoSoft rebrands). A change affects the whole family, grep `"device_file": "<name>"` in `models.py` first.
- Device modules are imported statically in `helpers.py` (`_DEVICE_MODULES`). Add new files there, do not use `importlib` at runtime.
- When renaming a device file, search the whole repository for the old name. Docstrings and test dict literals reference it as plain strings.
- A new model name must also be added to the matching bucket in `helpers.get_sensor_ala_map()`, otherwise alarm mapping silently falls back. `_SYR_CONNECT_SENSOR_ALA_CODES_SAFET` uses a different numbering than the shared NeoSoft dict.
