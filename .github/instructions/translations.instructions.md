---
description: Adding sensor keys, constants and translations
applyTo: "custom_components/syr_connect/{const.py,sensor.py,select.py,translations/*.json}"
---

# New keys and translations

- A new `getXXX` sensor key needs one `SyrConnectSensorEntityDescription` in `_SYR_CONNECT_SENSOR_TYPES` (`const.py`) with all its properties (device class, state class, unit, precision, entity category, enabled by default, `keep_as_string`) and an icon in `icons.json`. Mirror an existing similar key (for example `getBAR`). Check `sensor.py` for special-cased parsing by `_sensor_key`.
- Keys without known meaning are not added, even if present in a fixture.
- Add lowercase keys (`getxxx`) to all files in `translations/*.json`. Keep keys alphabetically sorted inside each object and use 2-space indentation.
- `entity.select.<key>` translations are separate from `entity.sensor.<key>`. Duplicate `name` (and `state` for enum selects) for every select.
- If a raw-to-display value map exists in `const.py`, reuse it to build select options. Do not duplicate it as translation `state` entries. Use translation `state` maps only for pure enums.
- Boolean switch-only keys need `_SYR_CONNECT_SWITCH_KNOWN_KEYS`, `_SYR_CONNECT_SENSOR_CONFIG`, an `entity.switch.<key>` icon in `icons.json` and a `switch.<key>` translation, but no sensor known-keys entry.
- Verify with `python scripts/find_missing_translations.py`.
