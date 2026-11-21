# aiosyrconnect

Asynchronous Python client for SYR Connect water treatment and leak protection devices
(SafeTech, Trio, NeoSoft, LEX, SafeFloor and the brands that share the SYR cloud).

It talks to two APIs:

- **XML API** of the SYR Connect cloud (`SyrConnectXmlAPI`): login, projects, devices,
  status, set commands and measurement histories. Requests carry a checksum, the login
  answer is AES encrypted.
- **JSON API** of the devices in the local network (`SyrConnectJsonAPI`, port 5333):
  status from `/get/all` and set commands, without the cloud.

## Requirements

- Python 3.14
- `aiohttp`, `defusedxml`, `pycryptodomex`

## Usage

The caller owns the `aiohttp.ClientSession` and names itself in the User-Agent.

```python
import aiohttp

from aiosyrconnect import (
    API_SERVICES,
    MODEL_SIGNATURES,
    SyrConnectAuthError,
    SyrConnectConnectionError,
    SyrConnectJsonAPI,
    SyrConnectXmlAPI,
)


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        cloud = SyrConnectXmlAPI(
            session,
            "user@example.com",
            "secret",
            service=API_SERVICES["de.consoft.syr.connect"],
            user_agent="aiosyrconnect/1.0.0",
            language="de-DE",
        )
        try:
            await cloud.login()
            for project in cloud.projects:
                for device in await cloud.get_devices(project["id"]):
                    status = await cloud.get_device_status(device["id"])
                    print(device["name"], status)
        except SyrConnectAuthError:
            ...  # wrong password: ask for new credentials
        except SyrConnectConnectionError:
            ...  # cloud not reachable or answer not usable: retry later

        neosoft = next(sig for sig in MODEL_SIGNATURES if sig.name == "neosoft5000")
        local = SyrConnectJsonAPI(
            session,
            host="192.168.1.20",
            model=neosoft,
            user_agent="aiosyrconnect/1.0.0",
        )
        devices = await local.get_devices("local")
        print(await local.get_device_status(devices[0]["id"]))
```

What the caller passes:

| Argument | Client | Purpose |
| --- | --- | --- |
| `session` | both | `aiohttp.ClientSession` of the caller |
| `user_agent` | both | HTTP User-Agent that names the caller; it does not imitate the SYR app. Required: a missing or empty value, leading or trailing whitespace or a control character raises `ValueError` |
| `service` | XML | Cloud service of the account, one of `API_SERVICES` |
| `language` | XML | Locale like `de-DE` for the requests; default `en-US` |
| `local_now` | XML | Returns the current time in the caller's time zone, for the UTC offset of the login; default the time zone of the process |
| `model` | JSON | Signature of the device model (`MODEL_SIGNATURES`); gives the local path of the JSON API |
| `login_required` | JSON | Whether the device needs ADM, as stored from an earlier `login_required`; default unknown |

## Device models

`MODEL_SIGNATURES` lists the known models: how a model is detected (`dk`, `dkv`, `sbt`
and `dfm` of the cloud, checks of the serial number, `getCNA` and `getVER`) and how it is
addressed (`base_path` of the local JSON API, the alarm commands).
`detect_model_signature()` returns the signature of a device, or None for an unknown
model:

```python
from aiosyrconnect import MODEL_SIGNATURES, detect_model_signature

signature = detect_model_signature(
    status,
    MODEL_SIGNATURES,
    dk=device.get("dk"),
    dkv=device.get("dkv"),
    sbt=device.get("sbt"),
)
```

A caller may extend `SyrConnectModelSignature` with fields of its own and pass its
signatures instead, in the order of `MODEL_SIGNATURES`: the status checks return the
first signature that matches.

## Errors

All errors derive from `SyrConnectError`.

| Error | Meaning |
| --- | --- |
| `SyrConnectAuthError` | Credentials rejected: ask for new ones |
| `SyrConnectConnectionError` | Not reachable or no usable answer: retry later |
| `SyrConnectLoginFailedError` | Login rejected for another cause than a wrong password (a `SyrConnectConnectionError`) |
| `SyrConnectSessionExpiredError` | Session token rejected again after one new login (a `SyrConnectConnectionError`) |
| `SyrConnectHTTPError` | HTTP error status of the local API, with `status` (a `SyrConnectConnectionError`) |
| `SyrConnectDeviceNotFoundError` | The XML client was asked for a device that is in no device list it fetched; devices are addressed by their serial number (`id`) |
| `SyrConnectInvalidResponseError` | Answer received but not usable, e.g. NSC or MIMA for a set command |

The library logs failures at debug level only and raises them; the caller decides what the
user sees. Logger names start with the package name.

## Protocol notes

- The client identity sent to the cloud (`CLIENT_*` in `const.py`) comes from a real
  capture of the SYR app. Do not "correct" it.
- Known quirks of the cloud and the devices are documented in
  `docs/known_issues_xml_api.md`, `docs/known_issues_json_api.md` and
  `docs/syrconnect-protocol.md` of the repository.

## License

Apache License 2.0.
