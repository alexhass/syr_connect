"""Tests for repairs platform."""

from unittest.mock import patch

from custom_components.syr_connect.const import DOMAIN
from custom_components.syr_connect.repairs import delete_issue
from homeassistant.core import HomeAssistant


async def test_delete_issue(hass: HomeAssistant) -> None:
    """Test deleting a repair issue."""
    with patch(
        "homeassistant.helpers.issue_registry.async_delete_issue"
    ) as mock_delete:
        delete_issue(hass, "test_issue_to_delete")

        mock_delete.assert_called_once_with(hass, DOMAIN, "test_issue_to_delete")
