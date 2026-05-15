#!/usr/bin/env python3
"""Debug script for tracing the XML API login process.

Usage:
    python scripts/debug_cli.py --username <email> --password <pw> [options]

Options:
    --username EMAIL            API account e-mail
    --password PASSWORD         API account password
    --base-url URL              API base URL (default: https://syrconnect.de)
    --api-app-name STRING       App name in login XML payload (default: "SYR Connect")
    --api-package-name STRING   Package name in app-version string (default: de.consoft.syr.connect)
    --user-agent STRING         HTTP User-Agent header (default: from const.py)
    --get-devices               Fetch device list for every project after login
    --get-status                Fetch device status for every device (implies --get-devices)
    --log-file PATH             Write output additionally to this file (no file written by default)
    --show-password             Show password in log output (default: masked as "***")
    --no-decrypt                Skip decryption step (show raw encrypted response)

Example (CLEAR PRO):
    python scripts/debug_cli.py \\
        --username me@example.com \\
        --password secret \\
        --base-url https://api.conelclearpro.de \\
        --api-app-name "CLEAR PRO" \\
        --api-package-name de.consoft.gc.conel.connect
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Make the custom_components package importable when running from repo root
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

import aiohttp  # noqa: E402  (after sys.path manipulation)

from custom_components.syr_connect.checksum import SyrChecksum  # noqa: E402
from custom_components.syr_connect.const import (  # noqa: E402
    _SYR_CONNECT_CLIENT_CF_BUNDLE_IDENTIFIER,
    _SYR_CONNECT_CLIENT_CF_BUNDLE_VERSION,
    _SYR_CONNECT_CLIENT_CHECKSUM_KEY1,
    _SYR_CONNECT_CLIENT_CHECKSUM_KEY2,
    _SYR_CONNECT_CLIENT_ENCRYPTION_IV,
    _SYR_CONNECT_CLIENT_ENCRYPTION_KEY,
    _SYR_CONNECT_CLIENT_OS_LANGUAGE,
    _SYR_CONNECT_CLIENT_OS_MODEL,
    _SYR_CONNECT_CLIENT_OS_NAME,
    _SYR_CONNECT_CLIENT_USER_AGENT,
)
from custom_components.syr_connect.encryption import SyrEncryption  # noqa: E402
from custom_components.syr_connect.http_client import HTTPClient  # noqa: E402
from custom_components.syr_connect.payload_builder import PayloadBuilder  # noqa: E402
from custom_components.syr_connect.response_parser import ResponseParser  # noqa: E402

# ---------------------------------------------------------------------------
# Logging setup â€” maximum verbosity on every relevant logger
# ---------------------------------------------------------------------------

def _setup_logging(log_file: str | None = None) -> None:
    fmt = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(fmt))
    root.addHandler(console)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(fmt))
        root.addHandler(file_handler)
        print(f"Logging to: {Path(log_file).resolve()}", flush=True)

    # Enable DEBUG on every syr_connect sub-module
    for name in [
        "custom_components.syr_connect.api_xml",
        "custom_components.syr_connect.http_client",
        "custom_components.syr_connect.payload_builder",
        "custom_components.syr_connect.response_parser",
        "custom_components.syr_connect.encryption",
        "custom_components.syr_connect.checksum",
    ]:
        logging.getLogger(name).setLevel(logging.DEBUG)

    # Also show aiohttp internals so we can see raw HTTP traffic
    logging.getLogger("aiohttp").setLevel(logging.DEBUG)
    logging.getLogger("aiohttp.client").setLevel(logging.DEBUG)


_LOG = logging.getLogger("debug_cli")


# ---------------------------------------------------------------------------
# Inline API client that accepts custom URLs and constants
# ---------------------------------------------------------------------------

class DebugXmlClient:
    """Stripped-down XML API client with configurable endpoints for debugging."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        username: str,
        password: str,
        base_url: str,
        app_version: str,
        app_name: str,
        api_package_name: str,
        user_agent: str,
        skip_decrypt: bool = False,
        show_password: bool = False,
    ) -> None:
        self.username = username
        self.password = password
        self.skip_decrypt = skip_decrypt
        self.show_password = show_password

        # Derived URLs from base_url (same path segments as production)
        self.login_url = f"{base_url}/WebServices/Api/SyrApiService.svc/REST/GetProjects"
        self.device_list_url = f"{base_url}/WebServices/SyrControlWebServiceTest2.asmx/GetProjectDeviceCollections"
        self.device_status_url = f"{base_url}/WebServices/SyrControlWebServiceTest2.asmx/GetDeviceCollectionStatus"

        _LOG.info("=== Endpoint configuration ===")
        _LOG.info("  base_url        : %s", base_url)
        _LOG.info("  login_url       : %s", self.login_url)
        _LOG.info("  device_list_url : %s", self.device_list_url)
        _LOG.info("  device_status_url : %s", self.device_status_url)
        _LOG.info("  app_version     : %s", app_version)
        _LOG.info("  api_app_name    : %s", app_name)
        _LOG.info("  api_package_name: %s", api_package_name)
        _LOG.info("  user_agent      : %s", user_agent)

        self.session_data: str = ""
        self.projects: list[dict] = []

        self.encryption = SyrEncryption(
            _SYR_CONNECT_CLIENT_ENCRYPTION_KEY,
            _SYR_CONNECT_CLIENT_ENCRYPTION_IV,
        )
        checksum = SyrChecksum(
            _SYR_CONNECT_CLIENT_CHECKSUM_KEY1,
            _SYR_CONNECT_CLIENT_CHECKSUM_KEY2,
        )
        self.payload_builder = PayloadBuilder(app_version, checksum, app_name)
        self.response_parser = ResponseParser()
        # For debugging runs, disable retrying to surface errors immediately
        self.http_client = HTTPClient(session, user_agent, max_retries=1)

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    async def login(self) -> bool:
        _LOG.info("=== LOGIN ===")
        _LOG.info("Username: %s", self.username)

        xml_data = self.payload_builder.build_login_payload(self.username, self.password)
        log_payload = xml_data if self.show_password else xml_data.replace(self.password, "***")
        _LOG.debug("--- Login request payload ---\n%s", log_payload)

        _LOG.info("POST %s", self.login_url)
        try:
            raw_response = await self.http_client.post(
                self.login_url,
                xml_data,
                content_type="text/xml",
            )
        except aiohttp.ClientResponseError as exc:
            _LOG.error(
                "HTTP %s %s\n  URL : %s\n  Hint: check --base-url",
                exc.status, exc.message, exc.request_info.url,
            )
            _LOG.debug("Full HTTP error details", exc_info=True)
            raise
        except aiohttp.ClientError as exc:
            _LOG.error("Connection error: %s\n  Hint: check --base-url and network", exc)
            _LOG.debug("Full connection error details", exc_info=True)
            raise
        _LOG.debug("--- Raw login response ---\n%s", raw_response)

        if self.skip_decrypt:
            _LOG.warning("--no-decrypt flag set â€” skipping decryption, cannot extract session.")
            return False

        _LOG.info("Parsing login response ...")
        encrypted_text, raw_parsed = self.response_parser.parse_login_response(raw_response)
        _LOG.debug("Encrypted session text length: %d chars", len(encrypted_text))
        _LOG.debug("parse_login_response extras: %s", raw_parsed)

        _LOG.info("Decrypting session data ...")
        decrypted = self.encryption.decrypt(encrypted_text)
        _LOG.debug("--- Decrypted session payload ---\n%s", decrypted)

        _LOG.info("Parsing decrypted session ...")
        self.session_data, self.projects = self.response_parser.parse_decrypted_login(decrypted)
        _LOG.info("Session token (first 20 chars): %s...", self.session_data[:20])
        _LOG.info("Projects found: %d", len(self.projects))
        for p in self.projects:
            _LOG.info("  Project: id=%s  name=%s", p.get("id"), p.get("name"))

        return True

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------

    async def get_devices(self, project_id: str) -> list[dict]:
        _LOG.info("=== GET DEVICES  project_id=%s ===", project_id)

        payload = self.payload_builder.build_device_list_payload(self.session_data, project_id)
        _LOG.debug("--- Device list payload ---\n%s", payload)

        _LOG.info("POST %s", self.device_list_url)
        raw_response = await self.http_client.post(
            self.device_list_url,
            {"xml": payload},
        )
        _LOG.debug("--- Raw device list response ---\n%s", raw_response)

        devices = self.response_parser.parse_device_list_response(raw_response)
        for dev in devices:
            dev["project_id"] = project_id
            if "id" not in dev and "serial_number" in dev:
                dev["id"] = dev["serial_number"]

        _LOG.info("Devices found: %d", len(devices))
        for dev in devices:
            _LOG.info(
                "  Device: id=%s  name=%s  dclg=%s",
                dev.get("id"),
                dev.get("name"),
                dev.get("dclg"),
            )
        return devices

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def get_status(self, device: dict) -> dict:
        device_id = device.get("id", "?")
        dclg = device.get("dclg", "")

        _LOG.info("=== GET STATUS  device=%s  dclg=%s ===", device_id, dclg)

        payload = self.payload_builder.build_device_status_payload(
            self.session_data, dclg
        )
        _LOG.debug("--- Status request payload ---\n%s", payload)

        _LOG.info("POST %s", self.device_status_url)
        raw_response = await self.http_client.post(
            self.device_status_url,
            {"xml": payload},
        )
        _LOG.debug("--- Raw status response (first 2000 chars) ---\n%s", raw_response[:2000])

        status = self.response_parser.parse_device_status_response(raw_response)
        _LOG.info("Status keys returned: %d", len(status))
        for k, v in sorted(status.items()):
            _LOG.info("  %-20s = %r", k, v)
        return status


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Debug the SYR Connect XML API login process with maximum logging.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--username", required=True, help="SYR Connect account e-mail")
    parser.add_argument("--password", required=True, help="SYR Connect account password")
    parser.add_argument(
        "--show-password",
        action="store_true",
        help="Show password in log output (default: masked as ***)",
    )
    parser.add_argument(
        "--base-url",
        default="https://syrconnect.de",
        help="API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--user-agent",
        default=_SYR_CONNECT_CLIENT_USER_AGENT,
        help="HTTP User-Agent header (default: %(default)s)",
    )
    parser.add_argument(
        "--api-app-name",
        default="SYR Connect",
        help="App name sent in the login XML payload v=\"...\" attribute (default: %(default)s)",
    )
    parser.add_argument(
        "--api-package-name",
        default=_SYR_CONNECT_CLIENT_CF_BUNDLE_IDENTIFIER,
        help="Package name embedded in the app-version string (default: %(default)s)",
    )
    parser.add_argument(
        "--get-devices",
        action="store_true",
        help="Fetch device list for every project after login",
    )
    parser.add_argument(
        "--get-status",
        action="store_true",
        help="Fetch device status for every device (implies --get-devices)",
    )
    parser.add_argument(
        "--no-decrypt",
        action="store_true",
        help="Skip decryption of login response (show raw XML only)",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        metavar="PATH",
        help="Write log output to this file in addition to stdout (default: debug_cli.log)",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    _LOG.info("Starting SYR Connect debug login script")
    _LOG.info("Python sys.path includes: %s", _REPO_ROOT)

    async with aiohttp.ClientSession() as session:
        effective_app_version = (
            f"App-{_SYR_CONNECT_CLIENT_CF_BUNDLE_VERSION}"
            f"-{_SYR_CONNECT_CLIENT_OS_LANGUAGE}"
            f"-{_SYR_CONNECT_CLIENT_OS_NAME}"
            f"-{_SYR_CONNECT_CLIENT_OS_MODEL}"
            f"-{args.api_package_name}"
        )

        client = DebugXmlClient(
            session,
            username=args.username,
            password=args.password,
            base_url=args.base_url,
            app_version=effective_app_version,
            app_name=args.api_app_name,
            api_package_name=args.api_package_name,
            user_agent=args.user_agent,
            skip_decrypt=args.no_decrypt,
            show_password=args.show_password,
        )

        try:
            ok = await client.login()
        except Exception as exc:
            _LOG.error("Login failed: %s", exc)
            _LOG.debug("Login traceback", exc_info=True)
            sys.exit(1)

        if not ok:
            _LOG.warning("Login returned False â€” aborting further steps.")
            return

        if args.get_devices or args.get_status:
            all_devices: list[dict] = []
            for project in client.projects:
                try:
                    devices = await client.get_devices(project["id"])
                    all_devices.extend(devices)
                except Exception as exc:
                    _LOG.error("Failed to get devices for project %s: %s", project.get("id"), exc)
                    _LOG.debug("Device list traceback", exc_info=True)

            if args.get_status:
                for device in all_devices:
                    try:
                        await client.get_status(device)
                    except Exception as exc:
                        _LOG.error("Failed to get status for device %s: %s", device.get("id"), exc)
                        _LOG.debug("Device status traceback", exc_info=True)

    _LOG.info("Done.")


def main() -> None:
    args = _parse_args()
    _setup_logging(args.log_file)
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

