"""Tests that every raised exception message and every alarm code is translated."""

import ast
import json
from pathlib import Path
import string
from typing import Any, cast

from custom_components.syr_connect.const import DOMAIN
from custom_components.syr_connect.models import MODELS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.translation import async_get_translations

_INTEGRATION = Path(__file__).parents[1] / "custom_components" / "syr_connect"


def _raised_translation_keys() -> dict[str, set[str]]:
    """Return the translation keys passed to exceptions, with their placeholder names."""
    keys: dict[str, set[str]] = {}
    for path in _INTEGRATION.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            kwargs = {kw.arg: kw.value for kw in node.keywords}
            key_node = kwargs.get("translation_key")
            if "translation_domain" not in kwargs or key_node is None:
                continue
            # A key is a string or a conditional expression choosing between strings
            key_values = (
                [key_node.body, key_node.orelse]
                if isinstance(key_node, ast.IfExp)
                else [key_node]
            )
            placeholders_node = kwargs.get("translation_placeholders")
            placeholders = (
                {k.value for k in placeholders_node.keys if isinstance(k, ast.Constant)}
                if isinstance(placeholders_node, ast.Dict)
                else set()
            )
            for value in key_values:
                assert isinstance(value, ast.Constant), path.name
                assert isinstance(value.value, str), path.name
                assert (
                    keys.setdefault(value.value, cast(Any, placeholders))
                    == placeholders
                ), f"{value.value} is raised with different placeholders"
    return keys


def test_raised_exceptions_are_translated() -> None:
    """Every translation_key of a raised exception exists in all languages, with its placeholders."""
    raised = _raised_translation_keys()
    assert raised

    for path in sorted((_INTEGRATION / "translations").glob("*.json")):
        exceptions = json.loads(path.read_text(encoding="utf-8"))["exceptions"]
        assert set(exceptions) == set(raised), path.name
        for key, placeholders in raised.items():
            message = exceptions[key]["message"]
            used = {
                name
                for _, name, _, _ in string.Formatter().parse(message)
                if name is not None
            }
            assert used == placeholders, f"{path.name}: {key}"


def test_alarm_codes_are_translated() -> None:
    """Every alarm code of every family has a state in getala and getalm in all languages.

    getALM is mapped with the alarm codes of the model (the LEX family reports its
    current alarm there); an empty getALM means no alarm.
    """
    ala_states: set[str] = set()
    for model in MODELS:
        if model.ala_codes is not None:
            ala_states.update(model.ala_codes.values())
    # An empty getALM means no alarm
    alm_states = ala_states | {"no_alarm"}

    for path in sorted((_INTEGRATION / "translations").glob("*.json")):
        sensors = json.loads(path.read_text(encoding="utf-8"))["entity"]["sensor"]
        assert ala_states <= set(sensors["getala"]["state"]), path.name
        assert alm_states <= set(sensors["getalm"]["state"]), path.name


def test_notification_and_warning_codes_are_translated() -> None:
    """Every notification and warning code of every family has a state in all languages."""
    not_states: set[str] = set()
    wrn_states: set[str] = set()
    for model in MODELS:
        if model.not_codes is not None:
            not_states.update(model.not_codes.values())
        if model.wrn_codes is not None:
            wrn_states.update(model.wrn_codes.values())

    for path in sorted((_INTEGRATION / "translations").glob("*.json")):
        sensors = json.loads(path.read_text(encoding="utf-8"))["entity"]["sensor"]
        assert not_states <= set(sensors["getnot"]["state"]), path.name
        assert wrn_states <= set(sensors["getwrn"]["state"]), path.name


async def test_exception_message_rendered_from_translation(hass: HomeAssistant) -> None:
    """Home Assistant renders a raised exception from the English translation."""
    # The message is only looked up for loaded integrations
    hass.config.components.add(DOMAIN)
    await async_get_translations(hass, "en", "exceptions", {DOMAIN})

    err = HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="set_value_failed",
        translation_placeholders={"device": "Keller", "entity": "Salzmenge"},
    )

    assert str(err) == "Could not set Salzmenge for the device Keller"
