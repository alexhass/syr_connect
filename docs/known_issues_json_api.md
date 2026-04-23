# Known issues — SYR JSON API

This document lists known deviations between the official SYR JSON API
documentation (https://iotsyrpublicapi.z1.web.core.windows.net/#einleitung)
and the behavior observed in real devices, the test fixtures in this
repository.

Purpose

- Provide a concise, actionable reference of non-conformant device
  behavior that the integration must tolerate.
- Point maintainers and integrators to the code and tests that implement
  the necessary workarounds.

Summary of major deviations

- **Missing `Content-Type: application/json` header:** Devices omit the `Content-Type` header and the `application/json` media type entirely; this is present across all devices and firmwares.
- **ADM login optional / 404:** The `/set/ADM/(2)f` login endpoint is not implemented on all firmwares and may return HTTP 404.
- **Percent-encoding issues:** Some firmwares reject percent-encoded path segments (e.g., `%3A`) and expect literal characters.
- **Response key and URL path casing inconsistencies:** `set` response keys and `/set` path segment casing vary between devices and firmwares.
- **Data-type inconsistencies:** Identical fields may appear as numbers, strings, or booleans depending on firmware/version.
- **API error-code case-sensitivity:** Error codes `NSC` and `MIMA` are expected uppercase; lowercased variants are treated as invalid.

Detailed deviations, impacts, and references

## 1. Missing `Content-Type` header

- Tentatively be considered a bug in current firmware.
- Description: All SYR devices return JSON without the `Content-Type: application/json` header. Devices use non-standard header casing (for example `content-length` in lowercase).
- Rationale (IANA / RFC): Per the IANA media types registry, `application/json` is the registered media type for JSON; HTTP semantics (RFC 7231) require senders to advertise the media type via `Content-Type`, and the JSON specification (RFC 8259) associates JSON with `application/json`. Devices SHOULD send `Content-Type: application/json; charset=utf-8` to ensure correct parsing, caching, and security behavior.
- Impact: HTTP clients that enforce a `Content-Type` check can fail to parse valid JSON responses.
- Mitigation in this project: The client uses `resp.json(content_type=None)` to tolerate missing or incorrect headers.
- Evidence / references:
  - Client: [custom_components/syr_connect/api_json.py](custom_components/syr_connect/api_json.py)

## 2. ADM login endpoint is optional (HTTP 404)

- To be considered as a good design change in newer devices.
- Description: The legacy ADM login (`/set/ADM/(2)f`) is required by some older firmwares (SafeTech v4 / Pontos) but absent on all newer devices. Devices without this endpoint typically return HTTP 404.
- Impact: Integrations must treat a 404 from the login endpoint as "login not required" instead of failing initialization.
- Mitigation in this project: `SyrConnectJsonAPI.login()` treats 404 as "login not required" and continues.
- Evidence / references:
  - Client: [custom_components/syr_connect/api_json.py](custom_components/syr_connect/api_json.py) (login handles 404)
  - Tests: [tests/test_api_json.py](tests/test_api_json.py) (test_login_404_treated_as_not_required)

## 3. Percent-encoding and literal special characters

- Tentavly be considered a bug in current firmware. Every webserver on this planet works this way except SYR devices.
- Description: Firmwares do not decode percent-encoded path components correctly. For example, `02:30` encoded as `02%3A30` may be rejected; the device expects the literal `:`.
- Impact: `set` requests must be sent with literal characters (no percent-encoding) to be accepted.
- Mitigation in this project: The client provides selective encoding (see `_construct_encoded_url` and `_build_set_url`).
- Quick reproduction (against a device):

```bash
# literal colon (required)
curl -i "http://localhost:5333/neosoft/set/RTM/02:30"

# percent-encoded (not accepted by firmwares)
curl -i "http://localhost:5333/neosoft/set/RTM/02%3A30"
```

## 4. `set` response key and URL path casing inconsistencies

- Tentatively be considered a bug in current firmware.
- Description: Devices are inconsistent in how they treat `set` commands and their responses:
  - **Response-key casing:** Neosoft devices return `set` response keys in lowercase (for example `{"setsv15":"OK"}`) while others return mixed/upper-case variants (for example `{"setSV15":"OK"}`).
  - **URL path casing:** Neosoft firmwares accept mixed-case path segments (e.g., `/set/SV/15`) while all other devices require lowercase paths (e.g., `/set/sv/15`).
- Impact: Sending the same logical command with different path casing can produce different response keys or cause the command to fail on devices that require lowercase. This breaks strict key matching and can cause higher-level logic to misinterpret results.
- Mitigation in this project: The client tolerates these inconsistencies by:
  - Performing case-insensitive matching for `set` response keys (`_validate_set_response`).
  - Normalizing `/set` path segments to lowercase when issuing commands to maximize compatibility.
- Examples:

```bash
# lowercase path -> Neosoft devices
curl -i "http://localhost:5333/neosoft/set/sv/15"  # -> {"setsv15":"OK"}

# mixed/upper-case path -> Neosoft devices
curl -i "http://localhost:5333/neosoft/set/SV/15"  # -> {"setSV15":"OK"}

# mixed/upper-case path -> all other devices (as documented)
curl -i "http://localhost:5333/trio/set/ab/false"  # -> {"setABtrue":"OK"}
```

- Evidence / references:
  - Client: [custom_components/syr_connect/api_json.py](custom_components/syr_connect/api_json.py)
  - Tests: [tests/test_api_json.py](tests/test_api_json.py)

## 5. Data-type inconsistencies

- Description: The same parameter can be delivered as different JSON types (number vs string) across devices and firmware versions. Examples include boolean-like values represented as the string `"true"`, and timestamps or counters delivered either as numbers or strings.
- Impact: Type-sensitive parsing or strict schemas can break; integrations should coerce and normalize types.
- Evidence / references:
  - Fixtures: [tests/fixtures/json/SafeTech_get_all.json](tests/fixtures/json/SafeTech_get_all.json), [tests/fixtures/json/NeoSoft2500_get_all.json](tests/fixtures/json/NeoSoft2500_get_all.json)

## 6. API error code inconsistencies (HTTP 404)

- Tentavly be considered a bug in current firmware.
- Trio DFRLS devices models only do not return an `"NSC"` value for unknown commands; instead the endpoint responds with HTTP 404 (Not Found). Impact: HTTP 404 causes the HTTP layer (`_execute_http_get`) to raise an HTTP/connection error instead of returning a JSON error code. Mitigation: callers should treat HTTP 404 from command endpoints as "no such command" where appropriate and handle it the same way as an `NSC` response.
- Evidence / references:
  - Client: [custom_components/syr_connect/api_json.py](custom_components/syr_connect/api_json.py) (`_execute_http_get()` HTTP 404 handling)
  - Tests: [tests/test_api_json.py](tests/test_api_json.py) (test_execute_http_get_404_error)

## 7. Documentation accuracy and misleading examples

- Tentatively be considered documentation defects.
- Description: The official SYR JSON API documentation contains incorrect or misleading examples. Implementers following the documented examples may expect typed JSON responses, but devices often reply with compact status keys. Example:

Documented for `GET /set/ab/true`:

```json
{"setAB": true}
```

Actual (expected) device response:

```json
{"setABtrue":"OK"}
```

Documented for `GET /set/pa3/true`:

```json
{"setPA3": true}
```

Actual (expected) device response:

```json
{"setPA3true":"OK"}
```

Documented for `GET /set/prf/2`:

```json
{"setPRF": 2}
```

Actual (expected) device response:

```json
{"setPRF2":"OK"}
```

- Impact: Relying on the documented shapes leads to parsing errors and incorrect client assumptions; the documentation is unreliable in multiple places.
- Mitigation in this project: The integration requires and expects the actual device response format — the compact status-key representation (e.g. {"setABtrue":"OK"}) — as the canonical representation. The documented typed JSON examples are not relied upon.
- Official incorrect documentation: [SYR JSON API documentation](https://iotsyrpublicapi.z1.web.core.windows.net/)

Recommendations

- Treat device responses as potentially non-conformant and normalize as needed (coerce numeric/boolean/string differences).
- Accept missing or incorrect `Content-Type` headers when parsing JSON.
- Treat 404 from the ADM login endpoint as "login not required." Do not fail the setup.
- Use case-insensitive matching for `set` response keys.
- Treat 404 from other endpoints as "no such command". (Trio defect)

Quick reproduction checklist

```bash
# 1) ADM login (may return 200 or 404 depending on firmware)
curl -i "http://localhost:5333/neosoft/set/ADM/(2)f"

# 2) Fetch all values
curl -i "http://localhost:5333/neosoft/get/all"

# 3) Fetch single value (missing key -> NSC)
curl -i "http://localhost:5333/neosoft/get/XYZ"

# 4) Set with literal special chars (required)
curl -i "http://localhost:5333/neosoft/set/RTM/02:30"

# 5) Fetch single value (missing key -> 404 http status code)
curl -i "http://localhost:5333/trio/get/XYZ"
```

References

- Official API documentation: https://iotsyrpublicapi.z1.web.core.windows.net/#einleitung
- Client code: [custom_components/syr_connect/api_json.py](custom_components/syr_connect/api_json.py)
- Tests: [tests/test_api_json.py](tests/test_api_json.py)
- Fixtures: [tests/fixtures/json/SafeTech_get_all.json](tests/fixtures/json/SafeTech_get_all.json), [tests/fixtures/json/NeoSoft2500_get_all.json](tests/fixtures/json/NeoSoft2500_get_all.json)
