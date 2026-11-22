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
addressed: `base_path` of the local JSON API, the status key of the alarm
(`alarm_status_key`) and the command that resets it (`alarm_reset_command()`). The value
of a set command comes from the client that sends it (`clear_value`: "FF" for the
cloud, 255 for the device); both clients send the command with `set_device_status`.
A signature also names the model (`display_name`, `manufacturer`, and per cloud service
`service_branding`, see `branded()`) and gives the limits of its settings
(`maximum_salt_volume`, `maximum_regeneration_interval`).
`detect_model_signature()` returns the signature of a device, or None for an unknown
model; `UNKNOWN_MODEL_SIGNATURE` names such a model ("Unknown model", no local path):

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

## Alarm, notification and warning codes

The devices report "no code" in getALA, getALM, getNOT and getWRN in several ways: `""`,
`0`, `00`, `FF`, `A0X0000` and, after a reset over the JSON API, `255`
(`NO_CODE_VALUES`). `is_code_active()` tells an active code from these values:

```python
from aiosyrconnect import is_code_active

if is_code_active(status.get(signature.alarm_status_key)):
    command, value = signature.alarm_reset_command(client.clear_value)
    await client.set_device_status(device_id, [(command, value)])
```

Every device family numbers its codes differently. The signature of a model names the
tables of its family: `ala_codes` (getALA, or getALM with `alarm_style_alm`),
`not_codes` (getNOT) and `wrn_codes` (getWRN). A table maps the code, in upper case, to
the key of its meaning; the caller translates the key. `None` means that the codes of
the family are unknown, so the caller shows the raw code:

```python
code = str(status.get(signature.alarm_status_key, "")).strip().upper()
meaning = signature.ala_codes.get(code) if signature.ala_codes is not None else None
```

## How a model reports its values

Besides the detection, a signature tells how the model reports its values, so the
caller can show them in the right unit:

| Field | Meaning |
| --- | --- |
| `whu_units` | Water hardness unit codes (getWHU) of the family: code -> unit (`WHU_UNITS_LEX`, `WHU_UNITS_MUCO`, `WHU_UNITS_NEOSOFT`) |
| `hardness_divisors` | The water hardness in another scale for a unit, e.g. tenths of mmol/l |
| `hardness_in_dh` | The water hardness stays in °dH whatever getWHU is set to (`WHU_FACTORS_FROM_DH`) |
| `value_divisors`, `value_factors` | Keys in another scale than on the other devices, e.g. ml or l/min |
| `inverted_flags` | Flags that mean the opposite, e.g. "disabled" |
| `local_time_timestamps` | getLAR is local wall time instead of UTC |
| `bat_in_percent`, `bar_is_system_pressure` | getBAT in %, getBAR as the pressure of the heating system |
| `cartridge_keys`, `cartridge_size_keys` | The key that holds the value of the installed cartridge type (getCRT) or size (getCRS) |
| `statistics` | Measurement history series the cloud keeps (`get_statistics()`) |

## Status values

The devices report many values in formats of their own, which differ per model and
API. `values.py` turns them into numbers and builds set commands in the format the
device expects:

| Function | Value |
| --- | --- |
| `is_value_true()` | Flags: `"1"`, `"True"`, `True`, `1` |
| `parse_net_value()`, `parse_bat_value()` | Voltages: `"ADC:950 6,16V"`, `"11,86"`, `"363"` |
| `parse_avo_value()` | Flow: `"1655mL"` -> 1.655 l |
| `parse_vol_value()`, `parse_lng_value()` | Values with a prefix or an annotation: `"Vol[L]6530"`, `"0 (0=Deutsch 1=English)"` |
| `parse_sta_value()` | Status of the regeneration -> key of the meaning |
| `get_iwh_value()` | Water hardness, estimated from the conductivity when the device does not report it |
| `get_rtm_value()`, `build_rtm_commands()` | Regeneration time as `HH:MM`, in one or two keys |
| `get_ab_value()`, `build_set_ab_command()` | Valve state: 1/2 or true/false |

The tables `CAS_VALUE_MAP`, `CRS_VALUE_MAP`, `LE_VALUE_MAP`, `T1_VALUE_MAP` and
`UL_VALUE_MAP` map a raw code to liters or hours:

```python
from aiosyrconnect import build_set_ab_command

command = build_set_ab_command(status, closed=True)
if command is not None:
    await client.set_device_status(device_id, [command])
```

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
