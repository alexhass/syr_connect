# Code Style

Conventions for all Python code in `custom_components/syr_connect/` and `tests/`. They describe how the existing code is written; new code must read like the code around it.

## Language and Tooling

- Target is Python 3.14 (`pyproject.toml`, `mypy.ini`). Every module starts with a docstring followed by `from __future__ import annotations`.
- Ruff is the linter: line length 120, rule sets `E`, `F`, `I` (import order), `W`, `N`, `UP`, `B`. Run it from the Windows virtualenv: `.venv/Scripts/ruff.exe check custom_components tests`.
- mypy checks `custom_components/syr_connect`: `.venv/Scripts/mypy.exe custom_components/syr_connect`. Add type hints to all new functions, even though `disallow_untyped_defs` is off.
- Pytest only runs in WSL, see `.github/instructions/tests.instructions.md`.
- Use the dedicated libraries already in `manifest.json`: `defusedxml` for parsing XML, `pycryptodomex` for AES. Do not add dependencies without asking.

## Naming

- Classes of this integration start with `SyrConnect` (`SyrConnectXmlAPI`, `SyrConnectDataUpdateCoordinator`).
- Internal constants live in `const.py` and start with `_SYR_CONNECT_` (`_SYR_CONNECT_API_XML_BASE_URL`). Constants that Home Assistant or other modules use as public names have no prefix (`DOMAIN`, `API_TYPE_JSON`, `CONF_*`).
- `const.py` is grouped by topic; within a group the constants are sorted alphabetically. Insert new constants at their alphabetical position, without splitting an existing alphabetical run.
- Constants that stay in their module, at module or class level, also start with `_SYR_CONNECT_` plus the module name (`_SYR_CONNECT_UPDATE_INSTALL_TIMEOUT_SECONDS`, `_SYR_CONNECT_SENSOR_VALUE_HANDLERS`). Exceptions are names Home Assistant requires, such as `PARALLEL_UPDATES` and `_LOGGER`.
- Device keys keep the protocol spelling: `getFLO`, `setAB`, `clrALA`. Translation keys use the lowercase form (`getflo`).
- Private helpers start with an underscore. Module-level helpers that several modules use go into `helpers.py`.

## Formatting for Small Diffs

- Write lists, sets, dicts and long argument lists with one entry per line and a trailing comma, so that adding or removing an entry changes exactly one line in the commit. Do not pack several entries on one line.
- Keep values that are maintained by hand (option maps, key lists, step lists) as literal entries. Generate them (`range`, comprehensions) only when they follow a documented rule, such as "0-95 in steps of 5", so that a change is a one-line change of that rule.
- When refactoring, keep existing code where it is and change only what the refactoring needs. Do not reformat, reorder or rewrite unrelated lines.

## Docstrings and Comments

- Every module, class and public function has a docstring. Use the Google style with `Args:`, `Returns:` and `Raises:` sections where they apply.
- The first docstring line is one sentence that says what the function does.
- Comments and docstrings are in English.
- Comments explain why something is done, especially protocol quirks and workarounds. Reference the issue in `docs/known_issues_xml_api.md` or `docs/known_issues_json_api.md` when a workaround exists because of one.
- Do not leave commented-out code or notes about the change history ("changed from …", "new: …").

## Logging

- Each module defines `_LOGGER = logging.getLogger(__name__)`.
- Pass arguments to the logger instead of formatting the message: `_LOGGER.debug("Device %s: %s", device_id, value)`, never an f-string.
- Levels: `debug` for request/response details, `info` for state changes the user may care about (login, set value), `warning` for recoverable problems, `error` for failures that stop an operation.
- What may be logged and what is masked is defined in `.github/instructions/logging.instructions.md`.

## Errors

- Raise the exceptions from `exceptions.py`. `SyrConnectError` is the base class. `SyrConnectAuthError` means the credentials are wrong and triggers a re-authentication. `SyrConnectConnectionError` (and its subclasses) means a network or server problem. `SyrConnectInvalidResponseError` means an answer that cannot be used.
- Chain exceptions with `raise ... from err`.
- Temporary connection problems are logged, and the entities keep their previous values. See the deliberate decisions in `AGENTS.md`.
- Do not catch `Exception` without logging it. Broad catches are only acceptable where a failure must never stop the caller (diagnostics, cleanup).

## Values and XML

- Check for missing values with `is None` / `is not None`. Device values can legitimately be `0`, `""` or empty collections.
- Parse XML only with `defusedxml`. Build request payloads with `xml.etree.ElementTree` so that values are escaped. Never build XML by string concatenation.
- Every XML request carries a checksum computed by `SyrChecksum`. When a request payload changes, the checksums in `tests/fixtures/xml/requests/` and in the `payload_builder.py` docstrings change too.

## Tests

- Every behaviour change comes with a test. Bug fixes get a test that fails without the fix.
- Fixtures live in `tests/fixtures/xml/` and `tests/fixtures/json/`. They are anonymised copies of real answers; keep their checksums valid (`tests/test_checksum.py` checks them).
- Further test rules are in `.github/instructions/tests.instructions.md`.
