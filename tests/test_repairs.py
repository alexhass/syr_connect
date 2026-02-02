"""Tests for repairs platform."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.syr_connect.const import DOMAIN
from custom_components.syr_connect.repairs import create_issue, delete_issue


async def test_create_issue(hass: HomeAssistant) -> None:
    """Test creating a repair issue."""
    with patch("homeassistant.helpers.issue_registry.async_create_issue") as mock_create:
        create_issue(
            hass,
            "test_issue",
            "test_translation_key",
            severity=ir.IssueSeverity.WARNING,
        )
        
        mock_create.assert_called_once_with(
            hass,
            DOMAIN,
            "test_issue",
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="test_translation_key",
        )


async def test_create_issue_with_kwargs(hass: HomeAssistant) -> None:
    """Test creating a repair issue with additional kwargs."""
    with patch("homeassistant.helpers.issue_registry.async_create_issue") as mock_create:
        create_issue(
            hass,
            "test_issue_2",
            "test_key",
            severity=ir.IssueSeverity.ERROR,
            data={"some": "data"},
            placeholders={"key": "value"},
        )
        
        mock_create.assert_called_once_with(
            hass,
            DOMAIN,
            "test_issue_2",
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="test_key",
            data={"some": "data"},
            placeholders={"key": "value"},
        )


async def test_delete_issue(hass: HomeAssistant) -> None:
    """Test deleting a repair issue."""
    with patch("homeassistant.helpers.issue_registry.async_delete_issue") as mock_delete:
        delete_issue(hass, "test_issue_to_delete")
        
        mock_delete.assert_called_once_with(hass, DOMAIN, "test_issue_to_delete")
