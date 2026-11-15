"""Answers of the SYR Connect XML API."""

from datetime import UTC, datetime
import logging
import math
import re
from typing import Any, NoReturn
from urllib.parse import unquote_plus

import defusedxml.ElementTree as etree

from .exceptions import (
    SyrConnectAuthError,
    SyrConnectLoginFailedError,
    SyrConnectSessionExpiredError,
)
from .models import SyrConnectApiDevice, SyrConnectStatus

_LOGGER = logging.getLogger(__name__)

# Text of a rejected login for a wrong password; always German
# (docs/known_issues_xml_api.md, issue 3)
_WRONG_PASSWORD_TEXT = "Benutzername und das Passwort stimmen nicht überein"

# Attributes of a <c> element that are kept next to its value, as "<name>_<attribute>"
_C_EXTRAS = (
    "dt",
    "m",
    "acd",
    "ih",
)


def _as_list(value: Any) -> list[Any]:
    """Return a parsed XML element list; a single element is parsed as a dict."""
    return value if isinstance(value, list) else [value]


def is_device_offline(dst: Any) -> bool:
    """Return True if the cloud device state means offline.

    dst="0" never online, dst="1" offline (2 = online, 3 = standby).

    Args:
        dst: The ``dst`` value of a status response

    Returns:
        True if the device is not reachable via the cloud
    """
    return str(dst if dst is not None else "").strip() in ("0", "1")


def _parse_utc_offset(value: Any) -> int | None:
    """Return a UTC offset (tzo) in seconds, or None if it is missing or invalid.

    Formats:
    - Summer time in Germany: "02:00:00" -> 7200
    - Negative offset: "-05:30:00" -> -19800
    """
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"(-)?(\d{1,2}):(\d{2})(?::(\d{2}))?", value.strip())
    if match is None:
        return None
    seconds = (
        int(match.group(2)) * 3600 + int(match.group(3)) * 60 + int(match.group(4) or 0)
    )
    return -seconds if match.group(1) else seconds


class ResponseParser:
    """Parse and validate SYR Connect API responses."""

    @staticmethod
    def validate_structure(data: dict, required_path: list[str]) -> bool:
        """Validate that a nested dictionary contains a required path.

        Args:
            data: Dictionary to validate
            required_path: List of keys representing the path to validate

        Returns:
            True if path exists, False otherwise
        """
        current = data
        for key in required_path:
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]
        return True

    @staticmethod
    def parse_xml(xml_string: str) -> dict[str, Any]:
        """Parse XML string to dictionary using ElementTree.

        Args:
            xml_string: XML string to parse

        Returns:
            Parsed dictionary representation of XML

        Raises:
            ValueError: If XML parsing fails
        """
        try:
            # defusedxml provides secure XML parsing by default (prevents XXE attacks)
            root = etree.fromstring(xml_string)
            # Wrap in root tag like xmltodict does
            return {root.tag: ResponseParser._element_to_dict(root)}
        except etree.ParseError as err:
            _LOGGER.debug("Failed to parse XML: %s", err)
            raise ValueError(f"Invalid XML response: {err}") from err

    @staticmethod
    def _element_to_dict(element: etree.Element) -> Any:
        """Convert XML element to dictionary.

        Args:
            element: XML element to convert

        Returns:
            Dictionary representation of the element
        """
        result: dict[str, Any] = {}

        # Add attributes with @ prefix
        if element.attrib:
            for key, value in element.attrib.items():
                result[f"@{key}"] = value

        # Handle child elements
        children = list(element)
        if children:
            child_dict: dict[str, Any] = {}
            for child in children:
                child_data = ResponseParser._element_to_dict(child)

                # Handle multiple children with same tag
                if child.tag in child_dict:
                    # Convert to list if not already
                    if not isinstance(child_dict[child.tag], list):
                        child_dict[child.tag] = [child_dict[child.tag]]
                    child_dict[child.tag].append(child_data)
                else:
                    child_dict[child.tag] = child_data

            result.update(child_dict)

        # Add text content if present
        if element.text and element.text.strip():
            text = element.text.strip()
            # If there are no children and no attributes, return just the text string
            if not children and not element.attrib:
                return text
            # Otherwise add it as #text key
            result["#text"] = text

        return result

    @staticmethod
    def _raise_if_session_expired(parsed: dict[str, Any]) -> None:
        """Raise SyrConnectSessionExpiredError if the webservice rejected the session token.

        An invalid or expired token is not answered with an HTTP error but with HTTP 200 and
        `<sc><msg v="Der Access-Token ist ungültig oder abgelaufen. ..." hl="Ungültiger Token !"
        mtid="1" /></sc>` instead of any data (see docs/known_issues_xml_api.md, issue 4).
        `mtid="1"` is used for detection because the texts are localized.
        """
        sc = parsed.get("sc")
        msg = sc.get("msg") if isinstance(sc, dict) else None
        if isinstance(msg, dict) and str(msg.get("@mtid", "")).strip() == "1":
            raise SyrConnectSessionExpiredError(
                f"Session token rejected: {msg.get('@v', '')}"
            )

    def raise_if_session_expired(self, xml_response: str) -> None:
        """Raise SyrConnectSessionExpiredError if a response rejects the session token.

        For responses that are otherwise not parsed (e.g. SetDeviceCollectionStatus).
        A response that is no XML at all is left to the caller.
        """
        try:
            parsed = self.parse_xml(xml_response)
        except ValueError:
            return
        self._raise_if_session_expired(parsed)

    def parse_login_response(self, xml_response: str) -> tuple[str, dict[str, Any]]:
        """Parse the login response and return its encrypted part.

        Args:
            xml_response: XML response string

        Returns:
            Tuple of (encrypted text of <api>, parsed response); the session ID and the
            projects are in the encrypted text (see parse_decrypted_login)

        Raises:
            ValueError: If response structure is invalid
        """
        parsed = self.parse_xml(xml_response)

        # Validate response structure
        if not self.validate_structure(parsed, ["sc", "api"]):
            raise ValueError("Authentication failed: Invalid login response structure")

        # The api element contains the encrypted session data as a string
        api_data = parsed["sc"]["api"]
        if isinstance(api_data, dict):
            # If it has attributes, the text is in #text
            encrypted_text = api_data.get("#text", "")
        else:
            # Otherwise it's a direct string
            encrypted_text = api_data

        return encrypted_text, parsed

    @staticmethod
    def is_login_successful(parsed: dict[str, Any]) -> bool:
        """Return True if a parsed login response reports success (<suc v="true"/>).

        The flag stands unencrypted next to <api> and is "false" for every rejected
        login, whatever the cause (see docs/known_issues_xml_api.md, issue 3).
        """
        sc = parsed.get("sc")
        suc = sc.get("suc") if isinstance(sc, dict) else None
        return isinstance(suc, dict) and str(suc.get("@v", "")).lower() == "true"

    def raise_login_rejected(self, decrypted_xml: str) -> NoReturn:
        """Raise the error for a rejected login (<suc v="false"/>).

        A wrong password is the only cause the server names, by the text of
        <msg v="...">. An unknown username and cloud outages get the same generic text,
        so they must not request a re-authentication (docs/known_issues_xml_api.md,
        issue 3).

        Args:
            decrypted_xml: Decrypted content of the login response

        Raises:
            SyrConnectAuthError: If the server rejected the password
            SyrConnectLoginFailedError: For every other cause
        """
        # Safe to log: a rejected login has no session token to leak
        _LOGGER.debug("Decrypted rejected login response: %s", decrypted_xml)
        try:
            parsed = self.parse_xml(f"<xml>{decrypted_xml}</xml>")
        except ValueError:
            parsed = {}
        root = parsed.get("xml")
        msg = root.get("msg") if isinstance(root, dict) else None
        server_message = msg.get("@v") if isinstance(msg, dict) else None
        detail = f" Message: {server_message}" if server_message else ""
        if isinstance(server_message, str) and _WRONG_PASSWORD_TEXT in server_message:
            raise SyrConnectAuthError(f"Invalid credentials.{detail}")
        raise SyrConnectLoginFailedError(f"Login rejected.{detail}")

    def parse_decrypted_login(
        self, decrypted_xml: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """Parse decrypted login data.

        Args:
            decrypted_xml: Decrypted XML string

        Returns:
            Tuple of (session_id, projects_list)

        Raises:
            ValueError: If structure is invalid
        """
        wrapped_xml = f"<xml>{decrypted_xml}</xml>"
        parsed = self.parse_xml(wrapped_xml)

        # Only called for a successful login (<suc v="true"/>), so a missing session is a
        # malformed answer, not rejected credentials
        if not self.validate_structure(parsed, ["xml", "usr", "@id"]):
            raise ValueError("Login succeeded but the response has no session")

        session_id = parsed["xml"]["usr"]["@id"]

        # Validate projects structure
        if not self.validate_structure(parsed, ["xml", "prs", "pre"]):
            raise ValueError(
                "Authentication succeeded but no projects found in account"
            )

        projects_data = parsed["xml"]["prs"]["pre"]

        projects = [
            {"id": project["@id"], "name": project["@n"]}
            for project in _as_list(projects_data)
        ]

        return session_id, projects

    def parse_device_list_response(
        self, xml_response: str
    ) -> list[SyrConnectApiDevice]:
        """Parse device list response.

        Args:
            xml_response: XML response string

        Returns:
            List of devices with their information; empty if the project has no devices

        Raises:
            ValueError: If the response contains no project (``sc>prs>pr``)
        """
        parsed = self.parse_xml(xml_response)
        self._raise_if_session_expired(parsed)

        # A valid answer always contains the project, even if it has no devices left
        # (see SyrTestDevice_GetProjectDeviceCollections_NoDevices.xml). Anything else
        # (error answer, maintenance page) must not be mistaken for an empty project,
        # because callers remove the devices missing from the list.
        if not self.validate_structure(parsed, ["sc", "prs", "pr"]):
            raise ValueError("Device list response contains no project.")

        # Device time values are local time (docs/known_issues_xml_api.md, issue 5). The
        # project reports the current UTC offset of its time zone, which the cloud
        # switches with daylight saving time.
        project = parsed["sc"]["prs"]["pr"]
        if isinstance(project, list):
            project = project[0]
        utc_offset = _parse_utc_offset(project.get("@tzo"))

        device_aliases, device_kind_versions = self._parse_device_collections(parsed)

        # Extract devices
        if not self.validate_structure(parsed, ["sc", "dvs"]):
            _LOGGER.debug("No 'dvs' element found in device list response")
            return []

        dvs = parsed["sc"]["dvs"]

        # Check if dvs contains 'd' element(s)
        if "d" in dvs:
            device_list = _as_list(dvs["d"])
        elif isinstance(dvs, dict) and "@dclg" in dvs:
            # dvs itself is a device
            device_list = [dvs]
        else:
            _LOGGER.debug("No devices found in 'dvs' element: %s", dvs)
            return []

        _LOGGER.debug("Found %d device(s) in response", len(device_list))

        devices: list[SyrConnectApiDevice] = []
        for device in device_list:
            if "@dclg" in device:
                devices.append(
                    self._build_device(
                        device, device_aliases, device_kind_versions, utc_offset
                    )
                )
            else:
                _LOGGER.debug("Skipping device without @dclg: %s", device)

        return devices

    def _parse_device_collections(
        self, parsed: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, int]]:
        """Return the aliases and the device kind versions of the device collections.

        The cloud reports both on the device collection (dcl), not on the device (d)
        itself.

        Args:
            parsed: Parsed device list response

        Returns:
            (alias by dclg, dkv by dclg); a device without a name has no alias
        """
        device_aliases: dict[str, str] = {}
        device_kind_versions: dict[str, int] = {}
        if not self.validate_structure(parsed, ["sc", "col"]):
            return device_aliases, device_kind_versions
        col = parsed["sc"]["col"]
        if "dcl" not in col:
            return device_aliases, device_kind_versions
        for dcl in _as_list(col["dcl"]):
            if "@dclg" in dcl and "@ali" in dcl:
                # URL-decode the alias (replace + with space and decode %XX sequences)
                alias = unquote_plus(dcl["@ali"])
                # A device without a name keeps its serial number as name
                if alias.strip():
                    device_aliases[dcl["@dclg"]] = alias
            if "@dclg" in dcl:
                device_kind_versions[dcl["@dclg"]] = int(dcl.get("@dkv") or 0)
        return device_aliases, device_kind_versions

    @staticmethod
    def _build_device(
        device: dict[str, Any],
        device_aliases: dict[str, str],
        device_kind_versions: dict[str, int],
        utc_offset: int | None,
    ) -> SyrConnectApiDevice:
        """Return a device of the device list from its <d> element.

        Args:
            device: The <d> element, with @dclg
            device_aliases: Alias by dclg, see _parse_device_collections
            device_kind_versions: dkv by dclg, see _parse_device_collections
            utc_offset: UTC offset of the project in seconds, if known
        """
        dclg_id = device["@dclg"]
        serial_number = device.get("@sn", "Unknown")
        device_name = device_aliases.get(dclg_id, serial_number)
        dk = int(device.get("@dk") or 0)
        dkv = device_kind_versions.get(dclg_id, 0)
        sbt = int(device.get("@sbt") or 0)

        _LOGGER.debug(
            "Adding device: %s (DCLG: %s, SN: %s, DK=%s, DKV=%s, SBT=%s)",
            device_name,
            dclg_id,
            serial_number,
            dk,
            dkv,
            sbt,
        )

        entry: SyrConnectApiDevice = {
            "id": serial_number,  # Use serial number as device ID
            "dclg": dclg_id,
            "serial_number": serial_number,
            "name": device_name,
            "dk": dk,
            "dkv": dkv,
            "sbt": sbt,
        }
        if utc_offset is not None:
            entry["utc_offset"] = utc_offset
        return entry

    def parse_device_status_response(
        self, xml_response: str
    ) -> SyrConnectStatus | None:
        """Parse device status response.

        Args:
            xml_response: XML response string

        Returns:
            Dictionary of status attributes or None if response is incomplete
        """
        parsed = self.parse_xml(xml_response)
        self._raise_if_session_expired(parsed)

        if "sc" not in parsed:
            _LOGGER.debug("No 'sc' element in status response")
            return None

        # Prefer responses that include the detailed device entries under
        # <dvs><d>...<c n="..." v="..."/>...</d></dvs>. If that detailed
        # structure is missing (e.g. response only contains <col><dcl .../>),
        # treat the response as incomplete and skip updating sensors.
        sc = parsed["sc"]
        if "dvs" not in sc:
            _LOGGER.debug(
                "Status response missing 'dvs' element; treating as incomplete: %s",
                sc.get("col"),
            )
            return None

        dvs = sc["dvs"]
        # Normalize device list
        device_list = None
        if isinstance(dvs, dict) and "d" in dvs:
            device_list = dvs["d"]
        elif isinstance(dvs, list):
            device_list = dvs
        elif isinstance(dvs, dict) and "@dclg" in dvs:
            device_list = [dvs]

        if not device_list:
            _LOGGER.debug(
                "Status response 'dvs' element contains no device entries; skipping update: %s",
                dvs,
            )
            return None
        device_list = _as_list(device_list)

        # If the response is broken (broken fragments), skip it.
        if self._ignore_broken_response(device_list):
            return None

        # Ensure at least one device entry contains detailed <c> children
        if not any(isinstance(d, dict) and "c" in d for d in device_list):
            _LOGGER.debug("Device entries in 'dvs' lack <c> children; skipping update")
            return None

        return self._flatten_attributes(parsed["sc"])

    def _ignore_broken_response(self, device_list: list[Any]) -> bool:
        """Ignore broken responses.

        Whenever the cloud returns nonsense, the response is ignored and the previous
        values are kept. This is a heuristic: there is no list of keys that makes a
        response complete, and it is not known which other broken answers the cloud
        sends. It is extended whenever a new broken answer is found.

        Dirty workaround:
        1. Syr Trio DFR/LS: For unknown reasons the device very often returns an XML
           response with getSRN, getALA, getNOT, getWRN only. This causes unwanted
           sensor status flapping. This needs to be ignored.

        Exception: devices the cloud reports offline (dst="0" never online, dst="1"
        offline) also answer with getSRN etc. only. That answer is passed on, so the
        caller can mark the device unavailable. These devices are skipped by the
        check; an online device in the same response is still checked.

        Resulting device states:
        - Offline (dst 0/1): passed on, the device becomes unavailable.
        - Back online (dst="2") with a full answer: passed on, the values are updated
          and the device is available again.
        - Back online (dst="2") with broken names only: ignored, the device keeps its
          previous state (stays unavailable) until a full answer arrives.

        Args:
            device_list: The <d> entries of the response

        Returns:
            True if the response is broken and must be ignored, otherwise False
        """
        # Detection: if every device that is not offline only contains minimal 'c'
        # entries with names in the broken set, treat as broken response.
        broken_names = {"getSRN", "getALA", "getNOT", "getWRN"}

        def get_c_names(d: Any) -> set[str]:
            """Return the names of the <c> elements of a <d> element."""
            if not isinstance(d, dict) or not d.get("c"):
                return set()
            return {
                item["@n"]
                for item in _as_list(d["c"])
                if isinstance(item, dict) and "@n" in item
            }

        # A device the cloud reports offline (dst="0" never online, dst="1" offline) has
        # no more data than this; its minimal answer is genuine, not the Trio glitch
        # (which comes from online devices, dst="2"). Parsing it lets the caller
        # mark the device unavailable instead of keeping it "available" with no status.
        # Exempt only the offline devices, so an online one in the same response is still
        # checked.
        online_devices = [
            d
            for d in device_list
            if not (isinstance(d, dict) and is_device_offline(d.get("@dst")))
        ]
        if not online_devices:
            return False

        # Collect the <c n="..."> names reported by each online device
        c_names_list = [get_c_names(d) for d in online_devices]

        # If every device has at least one c-name and all names are a subset
        # of the minimal broken set, ignore the response.
        if c_names_list and all(
            names and names.issubset(broken_names) for names in c_names_list
        ):
            _LOGGER.debug(
                "Ignoring status response: incomplete c-names present %s", c_names_list
            )
            return True

        # Only treat as broken when minimal c-names are present.
        return False

    def parse_statistics_response(
        self, xml_response: str
    ) -> list[tuple[datetime, float]]:
        """Parse the measurements (<sth dt v>) of a statistics response.

        See "SafeFloor measurement history" in docs/syrconnect-protocol.md for the
        format. The timestamps are UTC. Measurements without a valid timestamp or value
        are skipped.

        Args:
            xml_response: XML response string

        Returns:
            (timestamp, value) of every measurement, sorted by timestamp; empty if the
            response has no measurements or is an error message
        """
        parsed = self.parse_xml(xml_response)
        self._raise_if_session_expired(parsed)

        # Guard: require top-level 'sc' element before any further access
        if "sc" not in parsed:
            _LOGGER.debug("No 'sc' element in statistics response")
            return []

        # Check for API-level error message returned inside <sc>, e.g. for an unknown dclg
        if self.validate_structure(parsed, ["sc", "msg"]):
            _LOGGER.debug("Statistics API returned message: %s", parsed["sc"]["msg"])
            return []

        measurements: list[tuple[datetime, float]] = []
        for sth in self._find_elements(parsed["sc"], "sth"):
            raw_dt = sth.get("@dt")
            raw_value = sth.get("@v")
            try:
                timestamp = datetime.strptime(str(raw_dt), "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=UTC
                )
                value = float(str(raw_value).replace(",", "."))
            except ValueError:
                value = math.nan
            if not math.isfinite(value):
                _LOGGER.debug(
                    "Skipping measurement with invalid data: dt=%r v=%r",
                    raw_dt,
                    raw_value,
                )
                continue
            measurements.append((timestamp, value))
        return sorted(measurements)

    @staticmethod
    def _find_elements(data: Any, tag: str) -> list[dict[str, Any]]:
        """Return every element with this tag below a parsed XML structure.

        Args:
            data: Parsed XML structure (see parse_xml)
            tag: Tag of the elements to return

        Returns:
            The elements in document order
        """
        found: list[dict[str, Any]] = []
        if isinstance(data, list):
            for item in data:
                found.extend(ResponseParser._find_elements(item, tag))
        elif isinstance(data, dict):
            for key, value in data.items():
                if key == tag:
                    found.extend(
                        item for item in _as_list(value) if isinstance(item, dict)
                    )
                else:
                    found.extend(ResponseParser._find_elements(value, tag))
        return found

    @staticmethod
    def _add_c_values(result: dict[str, Any], value: Any) -> None:
        """Add the values of the <c n="..." v="..."> elements to a flattened status.

        By design: '@v' is required by the API spec on every <c> element. Elements
        that lack '@v' are malformed fragments and are silently skipped. If a
        shadow/pending value '@s' is present, the device has received a new setting
        but not yet applied it: '@s' is shown until it disappears (at which point '@v'
        holds the new value).

        Args:
            result: Flattened status to add the values to
            value: The parsed <c> element, or a list of them
        """
        for item in _as_list(value):
            if not (isinstance(item, dict) and "@n" in item and "@v" in item):
                continue
            name = item["@n"]
            result[name] = item["@s"] if "@s" in item else item["@v"]
            for extra in _C_EXTRAS:
                if f"@{extra}" in item:
                    result[f"{name}_{extra}"] = item[f"@{extra}"]

    @staticmethod
    def _flatten_attributes(data: dict | list) -> dict[str, Any]:
        """Flatten a parsed XML structure (see parse_xml) to one level.

        Attributes lose their ``@``, the values of ``<c>`` elements are added by their
        name (see _add_c_values), and the checksum ``<cs>`` is dropped. A later key
        overwrites an earlier one of the same name.

        Args:
            data: Parsed XML structure

        Returns:
            The flattened status
        """
        result: dict[str, Any] = {}

        if isinstance(data, dict):
            for key, value in data.items():
                # Skip checksum
                if key == "cs":
                    continue

                # Handle attributes (starting with @)
                if key.startswith("@"):
                    result[key[1:]] = value

                # Handle text content
                elif key == "#text":
                    result["_text"] = value

                # Handle 'c' tags which contain actual data
                elif key == "c":
                    ResponseParser._add_c_values(result, value)

                # Handle nested structures
                elif isinstance(value, dict | list):
                    nested = ResponseParser._flatten_attributes(value)
                    result.update(nested)

                # Handle simple values
                else:
                    result[key] = value

        elif isinstance(data, list):
            for item in data:
                nested = ResponseParser._flatten_attributes(item)
                result.update(nested)

        return result
