"""XML payload builder for SYR Connect API."""
from __future__ import annotations

import locale
import logging
from datetime import UTC, datetime, timedelta
from xml.sax.saxutils import escape

from .checksum import SyrChecksum

_LOGGER = logging.getLogger(__name__)


class PayloadBuilder:
    """Build XML payloads for SYR Connect API requests."""

    def __init__(self, app_version: str, checksum_calculator: SyrChecksum) -> None:
        """Initialize payload builder.

        Args:
            app_version: Application version string
            checksum_calculator: Checksum calculator instance
        """
        self.app_version = app_version
        self.checksum = checksum_calculator

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

    @staticmethod
    def _compute_locale_lang_reg() -> tuple[str, str]:
        """Return (lang, reg) based on system locale, defaults to en/US."""
        try:
            loc = locale.getdefaultlocale()[0]
            if not loc:
                return ("en", "US")
            # loc typically like 'en_US' or 'de_DE'
            parts = loc.replace('-', '_').split('_')
            lang = parts[0].lower() if parts else "en"
            reg = parts[1].upper() if len(parts) > 1 else "US"
            return (lang, reg)
        except Exception as err:
            _LOGGER.exception("Failed to determine locale language/region; falling back to en/US: %s", err)
            return ("en", "US")

    def build_login_payload(self, username: str, password: str) -> str:
        """Build login XML payload.

        Args:
            username: SYR Connect username
            password: SYR Connect password

        Returns:
            XML string for login request
        """
        timestamp = self.get_timestamp()
        # Escape username and password to prevent XML injection
        safe_username = escape(username)
        safe_password = escape(password)
        tzo = self._compute_local_tzo()
        lang, reg = self._compute_locale_lang_reg()
        payload = (
            f'<nfo v="SYR Connect" version="3.7.10" osv="15.8.3" '
            f'os="iOS" dn="iPhone" ts="{timestamp}" tzo="{tzo}" '
            f'lng="{lang}" reg="{reg}" />'
            f'<usr n="{safe_username}" v="{safe_password}" />'
        )
        return f'<?xml version="1.0" encoding="utf-8"?><sc><api version="1.0">{payload}</api></sc>'

    def build_device_list_payload(self, session_id: str, project_id: str) -> str:
        """Build device list XML payload with checksum.

        Args:
            session_id: Active session ID
            project_id: Project ID to query

        Returns:
            XML string with checksum
        """
        safe_session = escape(session_id)
        safe_project = escape(project_id)
        payload = (
            f'<?xml version="1.0" encoding="utf-8"?><sc>'
            f'<si v="{escape(self.app_version)}"/>'
            f'<us ug="{safe_session}"/>'
            f'<prs><pr pg="{safe_project}"/></prs>'
            f'</sc>'
        )
        return self._add_checksum(payload)

    def build_device_status_payload(self, session_id: str, device_id: str) -> str:
        """Build device status XML payload with checksum.

        Args:
            session_id: Active session ID
            device_id: Device ID to query

        Returns:
            XML string with checksum
        """
        safe_session = escape(session_id)
        safe_device = escape(device_id)
        payload = (
            f'<?xml version="1.0" encoding="utf-8"?><sc>'
            f'<si v="{escape(self.app_version)}"/>'
            f'<us ug="{safe_session}"/>'
            f'<col><dcl dclg="{safe_device}" fref="1"/></col>'
            f'</sc>'
        )
        return self._add_checksum(payload)

    def build_set_status_payload(
        self, session_id: str, device_id: str, command: str, value: int | str
    ) -> str:
        """Build set device status XML payload with checksum.

        Args:
            session_id: Active session ID
            device_id: Device ID to control
            command: Command name
            value: Command value

        Returns:
            XML string with checksum
        """
        safe_session = escape(session_id)
        safe_device = escape(device_id)
        safe_command = escape(command)
        safe_value = escape(str(value))
        payload = (
            f'<?xml version="1.0" encoding="utf-8"?><sc>'
            f'<si v="{escape(self.app_version)}"/>'
            f'<us ug="{safe_session}"/>'
            f'<col><dcl dclg="{safe_device}" fref="1">'
            f'<c n="{safe_command}" v="{safe_value}"/>'
            f'</dcl></col>'
            f'</sc>'
        )
        return self._add_checksum(payload)

    def build_statistics_payload(
        self, session_id: str, device_id: str, statistic_type: str = "water"
    ) -> str:
        """Build statistics XML payload with checksum.

        Args:
            session_id: Active session ID
            device_id: Device ID to query
            statistic_type: Type of statistics ("water" or "salt")

        Returns:
            XML string with checksum
        """
        safe_session = escape(session_id)
        safe_device = escape(device_id)
        base_payload = (
            f'<?xml version="1.0" encoding="utf-8"?><sc>'
            f'<si v="{escape(self.app_version)}"/>'
            f'<us ug="{safe_session}"/>'
            f'<col><dcl dclg="{safe_device}"></dcl></col>'
            f'</sc>'
        )

        # Add statistic-specific payload
        lang, reg = self._compute_locale_lang_reg()
        if statistic_type == "salt":
            stat_payload = f'<sh t="2" rtyp="1" lg="{lang}" rg="{reg}" unit="kg"/>'
        else:
            stat_payload = f'<sh t="1" rtyp="1" lg="{lang}" rg="{reg}" unit="l"/>'

        payload = base_payload.replace('></dcl>', f'>{stat_payload}</dcl>')
        return self._add_checksum(payload)

    def _add_checksum(self, payload: str) -> str:
        """Add checksum to XML payload.

        Args:
            payload: XML payload without checksum

        Returns:
            XML payload with checksum tag
        """
        checksum_value = self.checksum.compute_xml_checksum(payload)
        return payload.replace('</sc>', f'<cs v="{checksum_value}"/></sc>')


