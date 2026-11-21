---
description: Running and writing tests for syr_connect
applyTo: "tests/**"
---

# Tests

- Line coverage of `custom_components/syr_connect` must stay at 100 %. Run the tests with `--cov=custom_components.syr_connect --cov-report=term-missing:skip-covered` after every change and cover every reported line with a test. Do not add `# pragma: no cover` to reach it.
- A line that only patched builtins can reach (`round`, `re.match`, an `int` subclass with a raising `__float__`, a `dict` with a raising `__setitem__`) is unreachable: remove the branch instead of testing it (see `CODE_STYLE.md`, Errors).
- Pytest needs `fcntl` and does not run on Windows. Use WSL or the "Pytest (WSL)" task, never a Windows virtualenv.
- `MagicMock(spec=SyrConnectDataUpdateCoordinator)` exposes attributes without a default as random mocks. Set `entry_id` explicitly when the test depends on registry removal. `tests/conftest.py::create_mock_coordinator` sets it to `None`.
- Hand-written coordinator stand-ins (`class Dummy*Coord`) need `entry_id = None`.
- When adding a coordinator attribute used in registry removal, grep the tests for `async_remove.assert_called` and `.async_remove.called`.
- Select entities for `getPRF` and `getSRO` have no `_sensor_key`. Identify them with `isinstance(e, SyrConnectPrfSelect)` / `SyrConnectRotationSelect`.
- Do not tie generic detection tests to real `models.py` entries. Patch `models.MODELS` with a synthetic model; the tests of the library pass synthetic signatures to `detect_model_signature()`.
- After editing production code or tests that a revert touched, read both the code and its tests again before changing either.

## New Fixtures

Fixtures are copies of real answers. Before they are committed, every value that identifies a person, an account, a device or a home is replaced, with the replacement already used by the other fixtures:

| Value | Replacement |
| ------ | ------ |
| Serial number (`getSRN`, `sn`) | `123456789`, or the prefix of the model followed by `AAA12345` (`500AAA12345`) |
| Code number (`getCNO`) | `X` in the length of the real value |
| MAC address (`getMAC`, `getMAC1`, `getMAC2`, `mac`, `m`) | Manufacturer prefix (first three bytes) kept, the rest `XX:XX:XX`; further addresses of the same device `XX:XX:XY`, `XX:XX:XZ` |
| UUIDs (`pg`, `dclg`, `dg`, `dcg`, `pclg`, `ug`) | Random UUIDs; the same UUID gets the same replacement in every file of a device, so the references between project, device collection and device stay intact |
| IP addresses (`getWIP`, `getEIP`, `getIPA`) and gateways (`getWGW`, `getDGW`) | `192.168.178.20` and `192.168.178.1`; `0.0.0.0` and empty values stay |
| Wi-Fi name (`getWFC`) | `<brand>-<model>-wifi1` (`syr-trio-wifi1`) |
| E-mail address and password of the login | `user@example.com` and `secret` |
| Project name (`pn`) | `My+Project` |
| Contact (`com`) | `Firstname+Lastname` |
| Device name (`ali`) | `Example+<device kind>` (`Example+Water+Softener`) |
| Address, phone, fax, mobile, URL (`adr`, `zip`, `rsd`, `pho`, `fax`, `cph`, `url`) | Empty |

- Measured values, settings, firmware versions, model keys (`dk`, `dkv`, `sbt`, `getDFM`), time zone and country stay unchanged: the tests need them as the device sent them.
- A value that identifies the user and is not in the table is replaced as well. Ask the maintainer how before committing it.
- After anonymizing an XML answer, its checksum `<cs v="…"/>` is calculated again with `SyrChecksum(XML_CHECKSUM_KEY1, XML_CHECKSUM_KEY2).compute_element_checksum()` over the root element without `<cs>`. `tests/aiosyrconnect/test_xml_checksum.py` checks every fixture.
