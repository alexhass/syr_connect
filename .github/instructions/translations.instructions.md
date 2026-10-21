---
description: Adding sensor keys, constants and translations
applyTo: "custom_components/syr_connect/{const.py,sensor.py,select.py,switch.py,translations/*.json}"
---

# New keys and translations

- A new `getXXX` sensor key needs one `SyrConnectSensorEntityDescription` in `_SYR_CONNECT_SENSOR_TYPES` (`sensor.py`) with all its properties (device class, state class, unit, precision, entity category, enabled by default, `keep_as_string`, `divide_by`/`multiply_by` for scaled values, `value_fn` for a special format or a value map) and an icon in `icons.json`. Mirror an existing similar key (for example `getBAR`). Units that depend on another key (getIWH/getOWH, getBAT) are set in `SyrConnectSensor.__init__`.
- Keys without known meaning are not added, even if present in a fixture.
- Add lowercase keys (`getxxx`) to all files in `translations/*.json`. Keep keys alphabetically sorted inside each object and use 2-space indentation.
- A new select key needs a `SyrConnectSelectEntityDescription` in `_SYR_CONNECT_SELECT_TYPES` (`select.py`) and a block in `_build_device_selects`.
- `entity.select.<key>` translations are separate from `entity.sensor.<key>`. Duplicate `name` (and `state` for enum selects) for every select.
- If a raw-to-display value map exists in `const.py`, reuse it to build select options. Do not duplicate it as translation `state` entries. Use translation `state` maps only for pure enums.
- Boolean switch-only keys need a `SwitchEntityDescription` in `_SYR_CONNECT_SWITCH_TYPES` (`switch.py`), an `entity.switch.<key>` icon in `icons.json` and a `switch.<key>` translation, but no sensor supported-keys entry.
- Verify with `python scripts/find_missing_translations.py`.
