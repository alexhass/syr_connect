# Known issues — SYR JSON API

This document lists known deviations between the official SYR JSON API
documentation (https://iotsyrpublicapi.z1.web.core.windows.net/#einleitung)
and the behavior observed in real devices, the test fixtures in this
repository, and the local device emulator (see https://github.com/alexhass/syr_connect_emulator).

Purpose

- Provide a concise, actionable reference of non-conformant device
  behavior that the integration must tolerate.
- Point maintainers and integrators to the code and tests that implement
  the necessary workarounds.

Summary of major deviations

- **Missing Content-Type header:** Devices frequently return JSON without a `Content-Type` header.
- **ADM login optional / 404:** The `/set/ADM/(2)f` login endpoint is not implemented on all firmwares and may return HTTP 404.
- **Percent-encoding issues:** Some firmwares reject percent-encoded path segments (e.g., `%3A`) and expect literal characters.
- **Response key casing differences:** `set` responses may be returned in lowercase or mixed case by some firmwares.
- **Data-type inconsistencies:** Identical fields may appear as numbers, strings, or booleans depending on firmware/version.
- **API error-code case-sensitivity:** Error codes `NSC` and `MIMA` are expected uppercase; lowercased variants are treated as invalid.

Detailed deviations, impacts, and references

## 1. Missing `Content-Type` header

- Description: Many SYR devices return JSON without the `Content-Type: application/json` header. Devices use non-standard header casing (for example `content-length` in lowercase).
- Impact: HTTP clients that enforce a `Content-Type` check can fail to parse valid JSON responses.
- Mitigation in this project: The client uses `resp.json(content_type=None)` to tolerate missing or incorrect headers.
- Evidence / references:
  - Client: [custom_components/syr_connect/api_json.py](custom_components/syr_connect/api_json.py)

## 2. ADM login endpoint is optional (HTTP 404)

- Description: The legacy ADM login (`/set/ADM/(2)f`) is required by some firmwares but absent on others. Devices without this endpoint typically return HTTP 404.
- Impact: Integrations must treat a 404 from the login endpoint as "login not required" instead of failing initialization.
- Mitigation in this project: `SyrConnectJsonAPI.login()` treats 404 as "login not required" and continues.
- Evidence / references:
  - Client: [custom_components/syr_connect/api_json.py](custom_components/syr_connect/api_json.py) (login handles 404)
  - Tests: [tests/test_api_json.py](tests/test_api_json.py) (test_login_404_treated_as_not_required)

## 3. Percent-encoding and literal special characters

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

## 4. `set` response key casing inconsistencies

- Description: The canonical `set` response format is `{"set{CMD}{VALUE}": "OK"}`. Some firmwares (notably some Neosoft variants) return the CMD in lowercase (for example `{"setsv15":"OK"}` vs documented `{"setSV15":"OK"}`).
- Impact: Strict key matching fails; client must use case-insensitive matching to validate `set` responses.
- Mitigation in this project: `_validate_set_response` performs a case-insensitive lookup for the response key.
- Evidence / references:
  - Client: [custom_components/syr_connect/api_json.py](custom_components/syr_connect/api_json.py) (comment and code handling lowercase keys)
  - Tests: [tests/test_api_json.py](tests/test_api_json.py)

## 5. Data-type inconsistencies

- Description: The same parameter can be delivered as different JSON types (number vs string) across devices and firmware versions. Examples include boolean-like values represented as the string `"true"`, and timestamps or counters delivered either as numbers or strings.
- Impact: Type-sensitive parsing or strict schemas can break; integrations should coerce and normalize types.
- Evidence / references:
  - Fixtures: [tests/fixtures/json/SafeTech_get_all.json](tests/fixtures/json/SafeTech_get_all.json), [tests/fixtures/json/NeoSoft2500_get_all.json](tests/fixtures/json/NeoSoft2500_get_all.json)

## 6. API error code inconsistencies

- Device-specific (Trio): Trio models do not return an `"NSC"` value for unknown commands; instead the endpoint responds with HTTP 404 (Not Found). Impact: HTTP 404 causes the HTTP layer (`_execute_http_get`) to raise an HTTP/connection error instead of returning a JSON error code. Mitigation: callers should treat HTTP 404 from command endpoints as "no such command" where appropriate and handle it the same way as an `NSC` response.
- Evidence / references:
  - Client: [custom_components/syr_connect/api_json.py](custom_components/syr_connect/api_json.py) (`_execute_http_get()` HTTP 404 handling)
  - Tests: [tests/test_api_json.py](tests/test_api_json.py) (test_execute_http_get_404_error)

Recommendations

- Treat device responses as potentially non-conformant and normalize as needed (coerce numeric/boolean/string differences).
- Accept missing or incorrect `Content-Type` headers when parsing JSON.
- Treat 404 from the ADM login endpoint as "login not required." Do not fail the setup.
- Use case-insensitive matching for `set` response keys.
- Treat 404 from other endpoints as "no such command". (Trio defect)

Quick reproduction checklist

```bash
# 1) ADM login (may return 200 or 404 depending on fixture)
curl -i "http://localhost:5333/neosoft/set/ADM/(2)f"

# 2) Fetch all values
curl -i "http://localhost:5333/neosoft/get/all"

# 3) Fetch single value (missing key -> NSC)
curl -i "http://localhost:5333/neosoft/get/FOO"

# 4) Set with literal special chars (often required)
curl -i "http://localhost:5333/neosoft/set/RTM/02:30"

# 5) Fetch single value (missing key -> 404 http status code)
curl -i "http://localhost:5333/trio/get/FOO"
```

References
- Official API documentation: https://iotsyrpublicapi.z1.web.core.windows.net/#einleitung
- Client code: [custom_components/syr_connect/api_json.py](custom_components/syr_connect/api_json.py)
- Tests: [tests/test_api_json.py](tests/test_api_json.py)
- Fixtures: [tests/fixtures/json/SafeTech_get_all.json](tests/fixtures/json/SafeTech_get_all.json), [tests/fixtures/json/NeoSoft2500_get_all.json](tests/fixtures/json/NeoSoft2500_get_all.json)
