# Code Style

Conventions for all Python code in `custom_components/syr_connect/` and `tests/`. They describe how the existing code is written; new code must read like the code around it.

## Language and Tooling

- Target is Python 3.14 (`pyproject.toml`, `mypy.ini`). Every module starts with a docstring.
- Ruff is the linter. Its rules are taken over 1:1 from Home Assistant core. Run it from the Windows virtualenv: `.venv/Scripts/ruff.exe check .`.
- Ruff is also the formatter, with the settings of Home Assistant core (line length 88, double quotes). Run `.venv/Scripts/ruff.exe format .` after every change to Python code; unformatted code is not accepted. VS Code formats on save with the shared settings in `.vscode/settings.default.jsonc`.
- mypy checks `custom_components/syr_connect`, `scripts/` and `tests/` with the strict settings of Home Assistant core: `.venv/Scripts/mypy.exe`. Only `warn_unreachable` is off for the tests (see `mypy.ini`). Every function, also in tests, needs complete type hints, and methods that override a base class method are marked with `@override` (directly above `def`, below `@property`).
- Pytest only runs in WSL, see `.github/instructions/tests.instructions.md`.
- Use the dedicated libraries already in `manifest.json`: `defusedxml` for parsing XML, `pycryptodomex` for AES. Do not add dependencies without asking.

## Naming

- Classes of this integration start with `SyrConnect` (`SyrConnectXmlAPI`, `SyrConnectDataUpdateCoordinator`).
- Internal constants of the integration live in `const.py` and start with `_SYR_CONNECT_` (`_SYR_CONNECT_SCAN_INTERVAL_CONF`). The library has rules of its own, see Library aiosyrconnect. Constants that Home Assistant or other modules use as public names have no prefix (`DOMAIN`, `API_TYPE_JSON`, `CONF_*`).
- `const.py` is grouped by topic; within a group the constants are sorted alphabetically. Insert new constants at their alphabetical position, without splitting an existing alphabetical run.
- Constants that stay in their module, at module or class level, also start with `_SYR_CONNECT_` plus the module name (`_SYR_CONNECT_UPDATE_INSTALL_TIMEOUT`, `_SYR_CONNECT_SENSOR_VALUE_HANDLERS`). Exceptions are names Home Assistant requires, such as `PARALLEL_UPDATES` and `_LOGGER`.
- Device keys keep the protocol spelling: `getFLO`, `setAB`, `clrALA`. Translation keys use the lowercase form (`getflo`).
- Durations are `timedelta` constants in the largest unit that fits (`timedelta(minutes=30)`, `timedelta(hours=1)`), as in Home Assistant core, without a unit in the name (`_SYR_CONNECT_COORDINATOR_UNREACHABLE_TIMEOUT`). Plain numbers are only used where an interface takes a number; their name ends with the unit (`_DEFAULT_TIMEOUT_SECONDS` for `aiohttp.ClientTimeout`). Values of options and device keys keep the unit of the option or the protocol (the scan interval in seconds, `getRTM` values).
- Private helpers start with an underscore. Module-level helpers that several modules use go into the module of their topic in the `helpers/` package: `device.py` (device data of the coordinator), `integration.py` (version, scan interval, locale, hosts, HTTP responses), `profile.py` (device profile lookups) or `registry.py` (entity and device registry). The parsing of status values is protocol knowledge and belongs to the library (`aiosyrconnect/values.py`).

## Formatting for Small Diffs

- Write lists, sets, dicts and long argument lists with one entry per line and a trailing comma, so that adding or removing an entry changes exactly one line in the commit. Do not pack several entries on one line. This applies to values such as constants and maps. Imports follow the Home Assistant core rules, Ruff decides their layout. The formatter keeps a collection with a trailing comma at one entry per line, but joins a short collection without it into one line, so always write the trailing comma.
- Keep values that are maintained by hand (option maps, key lists, step lists) as literal entries. Generate them (`range`, comprehensions) only when they follow a documented rule, such as "0-95 in steps of 5", so that a change is a one-line change of that rule.
- When refactoring, keep existing code where it is and change only what the refactoring needs. Do not reformat, reorder or rewrite unrelated lines.

## Docstrings and Comments

- Every module, class and public function has a docstring. Use the Google style with `Args:`, `Returns:` and `Raises:` sections where they apply.
- The first docstring line is one sentence that says what the function does.
- Comments and docstrings are in American English (`behavior`, `synchronization`), as in Home Assistant core. `codespell` checks them, see `AGENTS.md`, Commands.
- A docstring about a device key names the value first and the key in parentheses: `"""Cartridge size (getCRS): raw value -> liters."""`, not `"""getCRS: raw value -> liters."""`.
- List several value formats or examples one per line, as `- <Model or case>: "<raw value>" -> <result>`, not several on one line:

  ```python
  """Mains voltage (getNET).

  Formats:
  - Safe-T+: "ADC:950 6,16V" -> 6.16 V
  - Safe-Tech+: "11,86" -> 11.86 V
  - Trio DFR/LS: "363" -> 3.63 V
  """
  ```

- Comments explain why something is done, especially protocol quirks and workarounds. Reference the issue in `docs/known_issues_xml_api.md` or `docs/known_issues_json_api.md` when a workaround exists because of one.
- Do not leave commented-out code or notes about the change history ("changed from …", "new: …").

## Library aiosyrconnect

The code that talks to the cloud and to the devices is the library `aiosyrconnect` in `custom_components/syr_connect/aiosyrconnect/`. It keeps the protocol separate from Home Assistant.

- The library imports neither Home Assistant nor a module of the integration, and only relative imports from its own package (`from .models import ...`, never `from ..const import ...`). `tests/aiosyrconnect/test_package.py` checks this, also for the tests of the library.
- What the integration uses is public: exported in `aiosyrconnect/__init__.py` (`__all__`), without leading underscore. The integration imports it from the package (`from .aiosyrconnect import SyrConnectXmlAPI`); only the tests and `scripts/debug_cli.py` import the modules of the library directly.
- Everything Home Assistant knows is passed in by the caller: the `aiohttp.ClientSession`, the `user_agent`, the locale (`language`) and the time zone (`local_now`). The library never creates or closes a session.
- The library holds the protocol knowledge: URLs, keys, checksums, encryption, the client identity of the app and the cloud services (`aiosyrconnect/const.py`), the requests and the parsing of the answers. It also knows the device models: which device kind (`dk`, `dkv`, `sbt`, `dfm`) and which status values identify a model, the local path of its JSON API, the commands it understands, its name, manufacturer and branding per cloud service and the limits of its settings (`aiosyrconnect/model_detection.py`, with `UNKNOWN_MODEL_SIGNATURE` for a model no signature matches), which values of getALA, getALM, getNOT and getWRN mean no code and what the codes of each device family mean (`aiosyrconnect/codes.py`: code -> key of the meaning, which the integration translates), and how the status values are reported and set (`aiosyrconnect/values.py`: the formats of single keys, the tables of raw codes and the set commands in the format of the device). Entities, the device profiles with their allowlists, translations and the registry stay in the integration; `models.py` adds the device profiles to the signatures of the library by the model name.
- Constants of the library have no `_SYR_CONNECT_` prefix, the package name says it already. Constants shared by its modules are in `aiosyrconnect/const.py` without leading underscore and named after their API (`XML_LOGIN_URL`, `XML_CHECKSUM_KEY1`, `JSON_SESSION_TIMEOUT`, `RESPONSE_SIZE_MAXIMUM`); constants of one module have a leading underscore only (`_PORT`, `_WRONG_PASSWORD_TEXT`).
- Comments and docstrings of the library speak of the caller, not of the coordinator, the config flow or the entities: the library does not know who uses it.
- The modules of the cloud start with `xml_` (`xml_api.py`, `xml_parser.py`, `xml_payload.py`, `xml_checksum.py`, `xml_encryption.py`), the local API is `json_api.py`. Data types are in `models.py`, the status values in `values.py`, the model signatures and their detection in `model_detection.py`, errors in `exceptions.py`.
- The tests of the library live in `tests/aiosyrconnect/`, one test module per library module (`test_xml_api.py` for `xml_api.py`). They use only the library and the fixtures in `tests/fixtures/`.
- A new third-party import of the library is added to the Requirements of `aiosyrconnect/README.md`; `tests/aiosyrconnect/test_package.py` checks this.

## Logging

- Each module defines `_LOGGER = logging.getLogger(__name__)`.
- Pass arguments to the logger instead of formatting the message: `_LOGGER.debug("Device %s: %s", device_id, value)`, never an f-string.
- Levels: `debug` for request/response details, `info` for state changes the user may care about (login, set value), `warning` for recoverable problems, `error` for failures that stop an operation.
- What may be logged and what is masked is defined in `.github/instructions/logging.instructions.md`.

## Errors

- Raise the exceptions from `aiosyrconnect/exceptions.py`. `SyrConnectError` is the base class. `SyrConnectAuthError` means the credentials are wrong and triggers a re-authentication. `SyrConnectConnectionError` (and its subclasses) means a network or server problem. `SyrConnectInvalidResponseError` means an answer that cannot be used. These errors do not derive from Home Assistant errors: the coordinator, the config flow and the entities catch them and raise the Home Assistant errors. The errors of the config flow (`CannotConnectError`, `InvalidAuthError`, ...) live in `config_flow.py`.
- Chain exceptions with `raise ... from err`.
- Temporary connection problems are logged, and the entities keep their previous values. See the deliberate decisions in `AGENTS.md`.
- Do not catch `Exception` without logging it. Broad catches are only acceptable where a failure must never stop the caller (diagnostics, cleanup).
- Catch only exceptions that real input can raise. No defensive `try`/`except` (or `contextlib.suppress`) around code that cannot fail: `int()` of a digit group matched by a regex, `round()` or `float()` of a number, `re` with a constant pattern, `str()` of a string, an assignment to a dict. Such a branch can only be tested by patching builtins and was removed on purpose; do not add it back.
- The API layer (the library `aiosyrconnect`) logs a failure at debug level and raises; it does not log it as warning or error, and does not log and re-raise. The coordinator, the config flow and the entities decide what the user sees, for example a failed update once instead of at every poll.

## Values and XML

- Check for missing values with `is None` / `is not None`. Device values can legitimately be `0`, `""` or empty collections.
- Parse XML only with `defusedxml`. Build request payloads with `xml.etree.ElementTree` so that values are escaped. Never build XML by string concatenation.
- Every XML request carries a checksum computed by `SyrChecksum`. When a request payload changes, the checksums in `tests/fixtures/xml/requests/` and in the `aiosyrconnect/xml_payload.py` docstrings change too.

## Tests

- Every behavior change comes with a test. Bug fixes get a test that fails without the fix.
- Line coverage of `custom_components/syr_connect` must stay at 100 %: no line without test coverage is accepted. Check it after every change (see `AGENTS.md`, Commands) and add tests for every uncovered line. Do not add `# pragma: no cover` to reach it.
- Fixtures live in `tests/fixtures/xml/` and `tests/fixtures/json/`. They are anonymized copies of real answers; what is replaced and how is described in `.github/instructions/tests.instructions.md`, New Fixtures. Keep their checksums valid (`tests/aiosyrconnect/test_xml_checksum.py` checks them).
- Further test rules are in `.github/instructions/tests.instructions.md`.
