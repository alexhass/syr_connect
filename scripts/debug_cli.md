# debug_cli.py - Command Reference

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

#### Login + device list + status

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --get-status
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

#### Login only

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --base-url https://api.conelclearpro.de `
    --api-app-name "CLEAR PRO" `
    --api-package-name de.consoft.gc.conel.connect
```

#### Login + device list

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --base-url https://api.conelclearpro.de `
    --api-app-name "CLEAR PRO" `
    --api-package-name de.consoft.gc.conel.connect `
    --get-devices
```

#### Login + device list + status

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --base-url https://api.conelclearpro.de `
    --api-app-name "CLEAR PRO" `
    --api-package-name de.consoft.gc.conel.connect `
    --get-status
```

#### With custom log file

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

#### Raw XML response without decryption

```powershell
python scripts/debug_cli.py `
    --username <username> `
    --password <password> `
    --base-url https://api.conelclearpro.de `
    --api-app-name "CLEAR PRO" `
    --api-package-name de.consoft.gc.conel.connect `
    --no-decrypt
```

