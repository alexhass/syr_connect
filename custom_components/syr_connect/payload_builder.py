"""XML payload builder for SYR Connect API."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from xml.etree import ElementTree as ET

from .checksum import SyrChecksum
from .const import (
    _SYR_CONNECT_CLIENT_CF_BUNDLE_VERSION,
    _SYR_CONNECT_CLIENT_OS_LANGUAGE,
    _SYR_CONNECT_CLIENT_OS_MODEL,
    _SYR_CONNECT_CLIENT_OS_NAME,
    _SYR_CONNECT_CLIENT_OS_VERSION,
)

_LOGGER = logging.getLogger(__name__)

_XML_DECLARATION = '<?xml version="1.0" encoding="utf-8"?>'


class PayloadBuilder:
    """Build XML payloads for SYR Connect API requests."""

    def __init__(
        self,
        app_version: str,
        checksum_calculator: SyrChecksum,
        app_name: str = "SYR Connect",
        language: str = _SYR_CONNECT_CLIENT_OS_LANGUAGE,
    ) -> None:
        """Initialize payload builder.

        Args:
            app_version: Application version string
            checksum_calculator: Checksum calculator instance
            app_name: Application name sent in the login payload ``<nfo v=...>``
            language: Locale like ``de-DE`` for ``lng``/``reg`` and ``lg``/``rg``
        """
        self.app_version = app_version
        self.checksum = checksum_calculator
        self.app_name = app_name
        self.language = language

    @staticmethod
    def get_timestamp() -> str:
        """Get current timestamp in required format.

        Returns:
            Formatted timestamp string
        """
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _compute_local_tzo() -> str:
        """Compute local timezone offset string in format ±HH:MM:SS.

        Uses the system local timezone at the current time to derive the
        offset. Returns a string like '01:00:00' or '-05:00:00'.
        """
        # Use the system local timezone offset at current time
        try:
            offset = datetime.now().astimezone().utcoffset() or timedelta(0)
            total_seconds = int(offset.total_seconds())
            sign = "+" if total_seconds >= 0 else "-"
            total_seconds = abs(total_seconds)
            hours, rem = divmod(total_seconds, 3600)
            minutes, seconds = divmod(rem, 60)
            return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"
        except Exception as err:
            _LOGGER.exception("Failed to compute local timezone offset (tzo); falling back to UTC: %s", err)
            # Fallback to UTC
            return "+00:00:00"

    def _compute_locale_lang_reg(self) -> tuple[str, str]:
        """Return (lang, reg) from the instance language, e.g. ``de-DE`` -> ``("de", "DE")``.

        The coordinator and config flow pass the Home Assistant locale (see
        `helpers.get_api_locale`). A language without region gets ``US``.
        """
        parts = self.language.replace("_", "-").split("-")
        lang = parts[0].lower()
        reg = parts[1].upper() if len(parts) > 1 else "US"
        return (lang, reg)

    @staticmethod
    def _element(parent: ET.Element | None, tag: str, **attrs: Any) -> ET.Element:
        """Create an element (optionally below ``parent``) with attributes in the given order.

        Values are converted to ``str``. ElementTree escapes them on serialisation,
        so no value can break out of its attribute or inject markup.

        Raises:
            TypeError: If a value is ``None``, so a missing session, device or project ID fails
                here instead of being sent to the API as the literal string ``"None"``.
        """
        element = ET.Element(tag) if parent is None else ET.SubElement(parent, tag)
        for name, value in attrs.items():
            if value is None:
                raise TypeError(f"XML attribute <{tag} {name}> must not be None")
            element.set(name, str(value))
        return element

    @staticmethod
    def _serialize(root: ET.Element) -> str:
        """Serialise an element tree to an XML string with the declaration the API expects."""
        return _XML_DECLARATION + ET.tostring(root, encoding="unicode")

    def _new_request(self, session_id: str) -> ET.Element:
        """Create the ``<sc>`` root with the ``<si>`` and ``<us>`` elements shared by all requests."""
        root = self._element(None, "sc")
        self._element(root, "si", v=self.app_version)
        self._element(root, "us", ug=session_id)
        return root

    def build_login_payload(self, username: str, password: str) -> str:
        """Build login XML payload.

        Args:
            username: SYR Connect username
            password: SYR Connect password

        Returns:
            XML string for login request

        Example (``tests/fixtures/xml/requests/ExampleRequest_Login.xml``)::

            <sc>
              <api version="1.0">
                <nfo v="SYR Connect" version="3.7.10" osv="15.8.3" os="iOS" dn="iPhone"
                     ts="2026-10-17 10:00:00" tzo="+02:00:00" lng="de" reg="DE" />
                <usr n="user@example.com" v="secret" />
              </api>
            </sc>
        """
        tzo = self._compute_local_tzo()
        lang, reg = self._compute_locale_lang_reg()
        root = self._element(None, "sc")
        api = self._element(root, "api", version="1.0")
        self._element(
            api,
            "nfo",
            v=self.app_name,
            version=_SYR_CONNECT_CLIENT_CF_BUNDLE_VERSION,
            osv=_SYR_CONNECT_CLIENT_OS_VERSION,
            os=_SYR_CONNECT_CLIENT_OS_NAME,
            dn=_SYR_CONNECT_CLIENT_OS_MODEL,
            ts=self.get_timestamp(),
            tzo=tzo,
            lng=lang,
            reg=reg,
        )
        self._element(api, "usr", n=username, v=password)
        return self._serialize(root)

    def build_device_get_list_payload(self, session_id: str, project_id: str) -> str:
        """Build device list XML payload with checksum.

        Args:
            session_id: Active session ID
            project_id: Project ID to query (UUID)

        Returns:
            XML string with checksum

        Example (``tests/fixtures/xml/requests/ExampleRequest_GetProjectDeviceCollections.xml``)::

            <sc>
              <si v="App-3.7.10-de-DE-iOS-iPhone-15.8.3-de.consoft.syr.connect"/>
              <us ug="9f3c1a52-7d4e-4b8a-a1c6-2e5d8b07f413"/>
              <prs><pr pg="8625a6fc-3547-45c4-b394-671b5c99b6b9"/></prs>
              <cs v="3825"/>
            </sc>
        """
        root = self._new_request(session_id)
        self._element(self._element(root, "prs"), "pr", pg=project_id)
        return self._add_checksum(root)

    def build_device_get_status_payload(self, session_id: str, device_id: str) -> str:
        """Build "get" device status XML payload with checksum.

        Args:
            session_id: Active session ID
            device_id: Device ID to query (UUID)

        Returns:
            XML string with checksum

        Example (``tests/fixtures/xml/requests/ExampleRequest_GetDeviceCollectionStatus.xml``)::

            <sc>
              <si v="App-3.7.10-de-DE-iOS-iPhone-15.8.3-de.consoft.syr.connect"/>
              <us ug="9f3c1a52-7d4e-4b8a-a1c6-2e5d8b07f413"/>
              <col><dcl dclg="0b09f7ce-41a0-4085-9e69-fa8827a32b6f" fref="1"/></col>
              <cs v="38DE"/>
            </sc>
        """
        root = self._new_request(session_id)
        self._element(self._element(root, "col"), "dcl", dclg=device_id, fref="1")
        return self._add_checksum(root)

    def build_device_set_status_payload(
        self,
        session_id: str,
        device_id: str,
        commands: list[tuple[str, Any]],
    ) -> str:
        """Build "set" device status XML payload with checksum.

        Args:
            session_id: Active session ID
            device_id: Device ID to control (UUID)
            commands: Sequence of ``(command, value)`` pairs, executed in order

        Returns:
            XML string with checksum

        Example (``tests/fixtures/xml/requests/ExampleRequest_SetDeviceCollectionStatus.xml``)::

            <sc>
              <si v="App-3.7.10-de-DE-iOS-iPhone-15.8.3-de.consoft.syr.connect"/>
              <us ug="9f3c1a52-7d4e-4b8a-a1c6-2e5d8b07f413"/>
              <col>
                <dcl dclg="0b09f7ce-41a0-4085-9e69-fa8827a32b6f" fref="1">
                  <c n="setAB" v="1"/>
                  <c n="setSIR" v=""/>
                </dcl>
              </col>
              <cs v="395A"/>
            </sc>
        """
        root = self._new_request(session_id)
        dcl = self._element(self._element(root, "col"), "dcl", dclg=device_id, fref="1")
        for cmd, val in commands:
            self._element(dcl, "c", n=cmd, v=val)
        return self._add_checksum(root)

    def build_device_get_statistics_payload(
        self, session_id: str, device_id: str, statistic_type: str = "water"
    ) -> str:
        """Build statistics XML payload with checksum.

        Args:
            session_id: Active session ID
            device_id: Device ID to query (UUID)
            statistic_type: Type of statistics ("water" or "salt")

        Returns:
            XML string with checksum

        Example for ``water`` (``tests/fixtures/xml/requests/ExampleRequest_GetStatistics_Water.xml``);
        ``salt`` uses ``t="2"`` and ``unit="kg"``::

            <sc>
              <si v="App-3.7.10-de-DE-iOS-iPhone-15.8.3-de.consoft.syr.connect"/>
              <us ug="9f3c1a52-7d4e-4b8a-a1c6-2e5d8b07f413"/>
              <col>
                <dcl dclg="0b09f7ce-41a0-4085-9e69-fa8827a32b6f">
                  <sh t="1" rtyp="1" lg="de" rg="DE" unit="l"/>
                </dcl>
              </col>
              <cs v="3C39"/>
            </sc>
        """
        root = self._new_request(session_id)
        dcl = self._element(self._element(root, "col"), "dcl", dclg=device_id)

        # Add statistic-specific element
        lang, reg = self._compute_locale_lang_reg()
        if statistic_type == "salt":
            self._element(dcl, "sh", t="2", rtyp="1", lg=lang, rg=reg, unit="kg")
        else:
            self._element(dcl, "sh", t="1", rtyp="1", lg=lang, rg=reg, unit="l")
        return self._add_checksum(root)

    def _add_checksum(self, root: ET.Element) -> str:
        """Serialise the request and append its checksum element.

        The checksum is computed over the request without the ``<cs>`` element. Any ``<cs>``
        already present is removed first, so calling this again on the same root yields the
        same request instead of a second ``<cs>`` and a checksum that includes the first.

        Args:
            root: ``<sc>`` element of the request

        Returns:
            XML string with the checksum element as last child of ``<sc>``
        """
        for old_checksum in root.findall("cs"):
            root.remove(old_checksum)
        checksum_value = self.checksum.compute_element_checksum(root)
        self._element(root, "cs", v=checksum_value)
        return self._serialize(root)
