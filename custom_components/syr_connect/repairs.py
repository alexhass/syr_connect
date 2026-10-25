"""Repairs platform for SYR Connect integration."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def delete_issue(hass: HomeAssistant, issue_id: str) -> None:
    """Delete a repair issue.

    Args:
        hass: Home Assistant instance
        issue_id: Unique identifier for the issue to delete
    """
    ir.async_delete_issue(hass, DOMAIN, issue_id)
