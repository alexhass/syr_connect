"""Per-device-model entity allowlist overrides.

Each module here is named after a `name` value from
`models.MODEL_SIGNATURES` (e.g. `conelclearprofill.py` for the model with
`"name": "conelclearprofill"`) and optionally defines one POSITIVE allowlist
constant per platform: `SENSOR_KNOWN_KEYS`, `SELECT_KNOWN_KEYS`,
`SWITCH_KNOWN_KEYS`, `BINARY_SENSOR_KNOWN_KEYS`, `BUTTON_KNOWN_KEYS`.

When present, `helpers.get_model_known_keys()` uses these instead of the
global allowlists in const.py, so the entities created for a device are
limited to keys explicitly confirmed for that model rather than the union of
every model's keys. Models without a file here keep using the global
const.py allowlists unchanged.
"""
