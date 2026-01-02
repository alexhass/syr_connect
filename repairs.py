"""Repairs platform for SYR Connect integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.repairs import RepairFlow, ConfirmRepairFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairFlow:
    """Create flow for repair issues.
    
    Args:
        hass: Home Assistant instance
        issue_id: The repair issue ID
        data: Optional data associated with the issue
        
    Returns:
        RepairFlow instance for the specific issue
    """
    if issue_id == "deprecated_entity":
        return ConfirmRepairFlow()
    
    return ConfirmRepairFlow()


def create_issue(
    hass: HomeAssistant,
    issue_id: str,
    translation_key: str,
    severity: ir.IssueSeverity = ir.IssueSeverity.WARNING,
    **kwargs: Any,
) -> None:
    """Create a repair issue.
    
    Args:
        hass: Home Assistant instance
        issue_id: Unique identifier for the issue
        translation_key: Translation key for the issue
        severity: Severity level of the issue
        **kwargs: Additional arguments to pass to create_issue
    """
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=severity,
        translation_key=translation_key,
        **kwargs,
    )


def delete_issue(hass: HomeAssistant, issue_id: str) -> None:
    """Delete a repair issue.
    
    Args:
        hass: Home Assistant instance
        issue_id: Unique identifier for the issue to delete
    """
    ir.async_delete_issue(hass, DOMAIN, issue_id)
