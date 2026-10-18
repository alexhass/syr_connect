# SYR Connect – Instructions for AI Agents

Home Assistant custom integration for SYR water treatment and leak protection devices. It talks to the SYR Connect cloud (XML API, `api_xml.py`) and to the local device API (JSON API, `api_json.py`). The code lives in `custom_components/syr_connect/`, the tests in `tests/`, the protocol documentation in `docs/`.

## Rules to Read First

All of these files apply. Read the matching ones before changing code.

| File | Applies to |
| ------ | ------ |
| `CODE_STYLE.md` | All Python code |
| `.github/copilot-instructions.md` | Home Assistant integration rules (links the upstream rules) |
| `.github/instructions/devices.instructions.md` | `devices/*.py`, `models.py`, `helpers.py` |
| `.github/instructions/entities.instructions.md` | Platforms, `unique_id`, entity registry |
| `.github/instructions/logging.instructions.md` | Logging and masking |
| `.github/instructions/markdown.instructions.md` | All Markdown files |
| `.github/instructions/tests.instructions.md` | `tests/` |
| `.github/instructions/translations.instructions.md` | New keys, `const.py`, `translations/*.json` |

## Commands

- Tests (WSL only): `wsl.exe bash -lc 'cd <repo path in WSL> && <WSL venv>/bin/python -m pytest --timeout=10 -q -p no:cacheprovider tests'`, or the VS Code task "Pytest (WSL)".
- Lint and types (Windows): `.venv/Scripts/ruff.exe check custom_components tests` and `.venv/Scripts/mypy.exe custom_components/syr_connect`.
- Git: use the Windows git only. WSL git reports nearly every file as modified because of line endings.

## Deliberate Decisions

These behaviours are intended. Do not change them and do not report them as findings in reviews.

- **Temporary errors keep old values.** Timeouts, routing errors, maintenance pages and failed polls are only logged. Entities keep their previous values: no `unavailable` state, no `UpdateFailed`, no repair issues. Only the very first refresh at setup may fail. A valid answer without a device means the device was deleted.
- **Offline devices.** The cloud reports `dst="0"` (never online) or `dst="1"` (offline); the coordinator then marks the device unavailable. After that, the device stays unavailable until a full status arrives, even if broken answers with `dst="2"` come first.
- **`_ignore_broken_response` stays broad.** It is a heuristic that drops every answer where the cloud returns nonsense. There is no list of keys that makes an answer complete, so it is extended when new broken answers turn up. Do not narrow it. The only exemption are offline devices (`dst` 0/1).
- **Diagnostics contact local devices.** For cloud entries, diagnostics call the local JSON API (including the ADM login `/set/ADM/(2)f`) at the device IP reported by the cloud, restricted to private addresses.
- **Client fingerprint.** The iOS, CFNetwork, Darwin and app version values in `const.py` come from a real capture of the SYR app. Do not "correct" them.
- **Debug logs are not masked**, except passwords and session tokens. See `.github/instructions/logging.instructions.md`.
