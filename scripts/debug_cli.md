# debug_cli.py - Command Reference

## Requirements

The script needs the dependencies of the project's virtualenv (`aiohttp`, Home Assistant, ...). Run it from the repository root with the virtualenv's Python:

```powershell
.venv\Scripts\python.exe scripts/debug_cli.py --username ... --password ...
```

Or activate the virtualenv first (`.venv\Scripts\activate.bat` in cmd, `.venv\Scripts\Activate.ps1` in PowerShell, `source .venv/bin/activate` on Linux/macOS); the examples below then work with `python`. If a module is missing, the script prints these instructions and exits.

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--username EMAIL` | *(required)* | SYR Connect account e-mail |
| `--password PASSWORD` | *(required)* | Account password |
| `--show-password` | - | Show password in log output (default: masked as `***`) |
| `--base-url URL` | `https://syrconnect.de` | API base URL |
| `--api-app-name STRING` | `SYR Connect` | API app name for login payload. Login fails if value is wrong. |
| `--api-package-name STRING` | `de.consoft.syr.connect` | Package name appended to the app-version string. |
| `--user-agent STRING` | `_SYR_CONNECT_CLIENT_USER_AGENT` from `const.py` | HTTP User-Agent header |
| `--list-devices` | - | List devices after login (prints `Project`, `id`, `dclg`, `name`) and exit |
| `--identity DEVICE` | - | Target device identifier (matches `id`, `dclg`, `serial_number` or `name`) for a one-shot set command |
| `--set-command CMD` | - | Set command to execute (e.g. `setSIR`, `setSV1`). Requires `--identity` and `--set-value` |
| `--set-value VALUE` | - | Value to use with `--set-command`. Parsed as `true`/`false` → bool, numbers → int/float, otherwise string |
| `--get-statistics [METHOD]` | - | Fetch the statistics of `--identity` and exit. Without `METHOD` the series of the device profile of the detected model (e.g. SafeFloor temperature and humidity); with `METHOD` one request with `--stat-t`, `--stat-unit` and `--stat-rtyp` |
| `--stat-t INT` | - | Measurement attribute `t` of `<sh>` (with `--get-statistics METHOD`) |
| `--stat-unit STRING` | - | Unit attribute `unit` of `<sh>`, e.g. `°C`, `%`, `l` (with `--get-statistics METHOD`) |
| `--stat-rtyp INT` | - | Report type attribute `rtyp` of `<sh>` (with `--get-statistics METHOD`) |
| `--get-devices` | - | Fetch device list for every project after login |
| `--get-status` | - | Fetch device status for every device (implies `--get-devices`) |
| `--no-decrypt` | - | Skip decryption, show raw XML response |
| `--log-file PATH` | *(none)* | Write log output to this file in addition to stdout |

---

## Examples

### SYR Connect (syrconnect.de)

#### Login only

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password>
```

#### Login + device list

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --get-devices
```

#### List devices (short, prints id/dclg/name and exits)

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --list-devices
```

#### Login + device list + status

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --get-status
```

#### One-shot set command (execute single set command and exit)

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --identity 123456789 `
    --set-command setSV1 `
    --set-value 10
```

Note: `--set-command` requires `--identity` and `--set-value`. The script parses `"true"`/`"false"` to booleans, numeric strings to `int`/`float`, otherwise the raw string is sent.

#### Statistics of a device

Fetches the statistics series of the device profile, for example the temperature and humidity history of a SafeFloor. The raw responses are logged at debug level; use `--log-file` to keep them.

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --identity 123456789 `
    --get-statistics
```

#### Try a statistics method

Sends one request to any statistics method (see "Statistics web services" in `docs/syrconnect-protocol.md`) with own request attributes. Without `unit` the cloud answers with an empty `<col />`.

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --identity 123456789 `
    --get-statistics GetLexPlusStatistics `
    --stat-t 1 `
    --stat-unit l `
    --stat-rtyp 1 `
    --log-file statistics.log
```

#### With custom log file

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --get-status `
    --log-file syr.log
```

#### Raw XML response without decryption

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --no-decrypt
```

---

### CLEAR PRO (api.conelclearpro.de)

#### CONEL Login only

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --base-url https://api.conelclearpro.de `
    --api-app-name "CLEAR PRO" `
    --api-package-name de.consoft.gc.conel.connect
```

#### CONEL Login + device list

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --base-url https://api.conelclearpro.de `
    --api-app-name "CLEAR PRO" `
    --api-package-name de.consoft.gc.conel.connect `
    --get-devices
```

#### CONEL Login + device list + status

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --base-url https://api.conelclearpro.de `
    --api-app-name "CLEAR PRO" `
    --api-package-name de.consoft.gc.conel.connect `
    --get-status
```

#### CONEL With custom log file

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --base-url https://api.conelclearpro.de `
    --api-app-name "CLEAR PRO" `
    --api-package-name de.consoft.gc.conel.connect `
    --get-status `
    --log-file conel.log
```

#### CONEL Raw XML response without decryption

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --base-url https://api.conelclearpro.de `
    --api-app-name "CLEAR PRO" `
    --api-package-name de.consoft.gc.conel.connect `
    --no-decrypt
```
