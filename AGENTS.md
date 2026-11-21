# SYR Connect – Instructions for AI Agents

Home Assistant custom integration for SYR water treatment and leak protection devices. It talks to the SYR Connect cloud (XML API) and to the local device API (JSON API) through the library `aiosyrconnect` (`custom_components/syr_connect/aiosyrconnect/`: `xml_api.py`, `json_api.py`), which must not depend on Home Assistant. The code lives in `custom_components/syr_connect/`, the tests in `tests/` (the tests of the library in `tests/aiosyrconnect/`), the protocol documentation in `docs/`.

## Rules to Read First

All of these files apply. Read the matching ones before changing code.

| File | Applies to |
| ------ | ------ |
| `CODE_STYLE.md` | All Python code |
| `.github/copilot-instructions.md` | Home Assistant integration rules (links the upstream rules) |
| `.github/instructions/devices.instructions.md` | `devices/*.py`, `models.py`, `helpers/*.py`, `aiosyrconnect/model_detection.py` |
| `.github/instructions/entities.instructions.md` | Platforms, `unique_id`, entity registry |
| `.github/instructions/logging.instructions.md` | Logging and masking |
| `.github/instructions/markdown.instructions.md` | All Markdown files |
| `.github/instructions/migrations.instructions.md` | `migrations.py`, migration steps in `__init__.py`, `VERSION` in `config_flow.py` |
| `.github/instructions/releases.instructions.md` | Version in `manifest.json`, minimum Home Assistant version in `hacs.json` |
| `.github/instructions/tests.instructions.md` | `tests/` |
| `.github/instructions/translations.instructions.md` | New keys, `const.py`, `translations/*.json` |

## Commands

- Tests (WSL only): `wsl.exe bash -lc 'cd <repo path in WSL> && <WSL venv>/bin/python -m pytest --timeout=10 -q -p no:cacheprovider tests'`, or the VS Code task "Pytest (WSL)".
- Coverage (WSL only): add `--cov=custom_components.syr_connect --cov-report=term-missing:skip-covered` to the test command. It must report 100 %; every uncovered line needs a test.
- Format (Windows): `.venv/Scripts/ruff.exe format .` after every change to Python code, before linting. `.venv/Scripts/ruff.exe format --check .` must report no changes.
- Lint and types (Windows): `.venv/Scripts/ruff.exe check .` and `.venv/Scripts/mypy.exe` (checks the integration, `scripts/` and `tests/`, see `files` in `mypy.ini`).
- Spelling (Windows): `.venv/Scripts/codespell.exe` checks code, comments and docs in American English. Its settings and the list of ignored words are in `[tool.codespell]` in `pyproject.toml`.
- German spelling (Windows and WSL): `prek run cspell --all-files` and `prek run german-compounds --all-files` check `README.de.md`. Known words are in `cspell.json`. prek replaces pre-commit, as in Home Assistant core, and uses the same `.pre-commit-config.yaml`.
- Git: Windows git and WSL git both work. `.gitattributes` forces LF line endings for every text file, as in Home Assistant core, independent of `core.autocrlf`.

## Deliberate Decisions

These behaviors are intended. Do not change them and do not report them as findings in reviews.

- **Temporary errors keep old values.** Timeouts, routing errors, maintenance pages and failed polls are only logged. Entities keep their previous values: no `unavailable` state, no `UpdateFailed`, no repair issues. Only the very first refresh at setup may fail. A valid answer without a device means the device was deleted.
- **Long failures are shown.** When a failure of the whole update, a project or a device lasts longer than 1 hour (`_SYR_CONNECT_COORDINATOR_UNREACHABLE_TIMEOUT`), it is no longer temporary: the affected entities become unavailable (`UpdateFailed` for the whole update, `available = False` for a project or device) and one repair issue per config entry (`unreachable_<entry_id>`, not fixable, not persistent) is shown. The issue has its own text (`unreachable_network`) when one of the errors is a network error (`is_network_error`: host name not resolved or no connection opened), because the user can check the own network and DNS. Everything else, including timeouts and unusable answers, gets the general text: the SYR Connect cloud gives no reliable error answers (it answers with HTTP 200), so no text blames the cloud. Both end with the first update without such a failure. Polling never stops: while the whole update fails, the update interval doubles after every failed update up to 15 minutes (`_SYR_CONNECT_COORDINATOR_BACKOFF_MAXIMUM`), and the first successful update restores the configured interval. A failing project or device does not change the interval.
- **Offline devices.** The cloud reports `dst="0"` (never online) or `dst="1"` (offline); the coordinator then marks the device unavailable. After that, the device stays unavailable until a full status arrives, even if broken answers with `dst="2"` come first.
- **`_ignore_broken_response` stays broad.** It is a heuristic that drops every answer where the cloud returns nonsense. There is no list of keys that makes an answer complete, so it is extended when new broken answers turn up. Do not narrow it. The only exemption are offline devices (`dst` 0/1).
- **Diagnostics contact local devices.** For cloud entries, diagnostics call the local JSON API (including the ADM login `/set/ADM/(2)f`) at the device IP reported by the cloud, restricted to private addresses.
- **Client fingerprint.** The iOS and app version values of the XML payload in `aiosyrconnect/const.py` come from a real capture of the SYR app. Do not "correct" them. The HTTP User-Agent does not imitate the app; it names the integration and Home Assistant, so that SYR can tell the requests apart from app traffic.
- **Unique IDs of the config entries.** A local entry is identified by the serial number of its device, a cloud entry by service and lowercased username: the cloud has no account ID and ignores the letter case of the username, which is a name or an e-mail address. The same device may be set up both through the cloud and locally; the two entries have devices and entities of their own.
- **Debug logs are not masked**, except passwords and session tokens. See `.github/instructions/logging.instructions.md`.
