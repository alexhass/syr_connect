---
description: Adding sensor keys, constants and translations
applyTo: "custom_components/syr_connect/{const.py,sensor.py,select.py,switch.py,translations/*.json}"
---

# New keys and translations

- A new `getXXX` sensor key needs one `SyrConnectSensorEntityDescription` in `_SYR_CONNECT_SENSOR_TYPES` (`sensor.py`) with all its properties (device class, state class, unit, precision, entity category, enabled by default, `keep_as_string`, `divide_by`/`multiply_by` for scaled values, `value_fn` for a special format or a value map, `hidden_when` for a sensor that is hidden while its value is empty, or `hidden_when="always"` for a documented key that must not become an entity until a device reports a useful value) and an icon in `icons.json`. Mirror an existing similar key (for example `getBAR`). Units that depend on another key (getIWH/getOWH, getBAT) are set in `SyrConnectSensor.__init__`.
- Keys without known meaning are not added, even if present in a fixture.
- Add lowercase keys (`getxxx`) to all files in `translations/*.json`. Keep keys alphabetically sorted inside each object and use 2-space indentation.
- A new select key needs a `SyrConnectSelectEntityDescription` in `_SYR_CONNECT_SELECT_TYPES` (`select.py`) and a block in `_build_device_selects`.
- `entity.select.<key>` translations are separate from `entity.sensor.<key>`. Duplicate `name` (and `state` for enum selects) for every select.
- If a raw-to-display value map exists in `const.py`, reuse it to build select options. Do not duplicate it as translation `state` entries. Use translation `state` maps only for pure enums.
- Boolean switch-only keys need a `SwitchEntityDescription` in `_SYR_CONNECT_SWITCH_TYPES` (`switch.py`), an `entity.switch.<key>` icon in `icons.json` and a `switch.<key>` translation, but no sensor supported-keys entry.
- Every exception that Home Assistant shows to the user (`HomeAssistantError`, `ServiceValidationError`, `ConfigEntryNotReady`, `ConfigEntryAuthFailed`, `UpdateFailed`) is raised with `translation_domain=DOMAIN`, `translation_key` and `translation_placeholders`, never with a message string. Add the key to `exceptions` in all files in `translations/*.json`. `tests/test_translations.py` checks keys and placeholders.
- Exception messages name the device by its name (`{device}`: `self._device_name`) and the entity by its translated name (`{entity}`: `self._entity_name`). They never contain the serial number, protocol keys (`getALM`) or the technical error text; log the error with `_LOGGER.error` before raising instead. Use separate keys for different situations (alarm, notification, warning) rather than a placeholder for the kind.
- Placeholders in messages stand without quotes, as in Home Assistant core (`The device {device} has no active alarm to reset`).
- Verify with `python scripts/find_missing_translations.py`.

## Wording

- Every language uses one term per concept across all strings (backwash, microleakage, conductivity, leak protection). Check the existing strings of the language before adding a new one.
- A qualifier after a name goes in parentheses: `Buzzer (profile 1)`, `Aborted (pressure drop)`, `Leak protection level (present)`. No dash constructions (`Leakage protection - Present level`) and no bare appended words (`Regenerationszyklen Anzahl`).
- A container, tank or bottle is named with the preposition of the language instead of parentheses: `Salt volume in container 1`, `Salzmenge in Behälter 1`, `Quantité de sel dans le réservoir 1`, `Ilość soli w pojemniku 1`.
- Use the normal hyphen (`-`), never the non-breaking hyphen (U+2011). Names and states end without a period.
- English is American English (`Synchronization`) in sentence case (`Cloud access`, `SYR Connect options`).
- German: join compounds, never split them with a space ("Deppenleerzeichen"). Join with a hyphen where a part is an abbreviation, a name or would be hard to read: `MAC-Adresse`, `WLAN-Signalstärke`, `Software-Update`, `SYR-Connect-Gerät`, `Mikroleckage-Test-Intervall`. The qualifier in parentheses starts with a capital letter: `Regenerationen (Gesamt)`, `Temperatur (Minimal)`; the other languages keep it lowercase.
- Dutch joins compounds as German does: `Microlektestinterval`, `Wi-Fi-signaalsterkte`, `SYR Connect-apparaat`.
- French puts a space before `:` and uses straight apostrophes (`'`).
- `pt.json` is European Portuguese (`utilizador`, `palavra-passe`, `ligação`, `fuga`, `caudal`, `a abrir`), not Brazilian Portuguese.
