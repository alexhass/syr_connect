"""Tests that every raised exception message is translated."""

import ast
import json
from pathlib import Path
import string
from typing import Any, cast

from custom_components.syr_connect.const import DOMAIN
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
