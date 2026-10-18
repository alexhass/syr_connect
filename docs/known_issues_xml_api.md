# Known issues — SYR XML API

This document lists known deviations between the official SYR Connect XML
API behaviour and what this integration observes in the wild, in the
test fixtures, and in the parsing/encryption layers implemented here.

## Purpose

- Provide a concise, actionable reference of non-conformant XML API
  behaviour the integration must tolerate.
- Point maintainers to the code and tests that implement the necessary
  workarounds.

## Detailed deviations, impacts and references

### 1. Minimal/broken responses are intentionally ignored

- Tentatively be considered a bug on SYR server.
- Description: Some devices (notably Trio DFR/LS series) occasionally
  return responses containing only a tiny set of `c` names
  (`getSRN`, `getALA`, `getNOT`, `getWRN`). These fragments are treated
  as broken and ignored to avoid spurious sensor updates.
- Impact: Partial but valid responses containing only those names will be skipped as a conservative choice to prevent state flapping.
- Mitigation in this project:
  - Ignores broken responses: `_ignore_broken_response()` in `custom_components/syr_connect/response_parser.py` implements this heuristic.

### 2. Offline devices return incorrect data types

- Tentatively be considered part of the design, but it is not ideal.
- Description: API may return incorrect data types if device is offline.
- Impact: Valid responses containing correct setting values, but all device measurements return empty strings and not the last known state. Causing unexpected data type errors in Python.
- Mitigation in this project: Check for dst="0" ("never been online") or dst="1" ("offline" status) and set all values as unknown.

### 3. Rejected login returns HTTP 200 with a generic error message

- Tentatively be considered part of the design, but it is not ideal.
- Description: A login (`GetProjects`) with an unknown username or a wrong password is not answered with an HTTP error. The server returns HTTP 200 and a regular, correctly encrypted `<sc><api>…</api></sc>` response. Only the decrypted content differs: it has no `<usr id="…">` session and no `<prs>` projects, but a `<msg>` element instead. Observed decrypted responses (2026-10-17):

  - Unknown username and password:

    ```xml
    <nfo v="SyrConnect.Api.GetProjects" version="1.0.0" ts="2026-10-17 21:31:37" tzo="00:00:00" lng="de" reg="DE" />
    <app id="1" />
    <ags />
    <msg hl="Fehler" v="Der Vorgang konnte nicht durchgeführt werden." typ="1" />
    ```

  - Known username, wrong password:

    ```xml
    <nfo v="SyrConnect.Api.GetProjects" version="1.0.0" ts="2026-10-17 21:34:56" tzo="00:00:00" lng="de" reg="DE" />
    <app id="1" />
    <ags />
    <msg hl="Fehler" v="Der Benutzername und das Passwort stimmen nicht überein." typ="1" />
    ```

  A successful login contains `<usr id="<session token>" …/>` and `<prs><pre id="<project id>" n="<project name>" …/></prs>` instead of `<msg>`.
- Impact: The HTTP status cannot distinguish rejected credentials from a successful login. The `<msg>` text differs by cause: for an unknown username it is generic ("The operation could not be performed"), only for a known username with a wrong password it names the problem ("Username and password do not match"). The text is always German, whatever locale is sent (see issue 4), and does not exist for every cause, so it is not used for detection.
- Mitigation in this project:
  - A decrypted login response without `usr@id` is treated as rejected credentials: `parse_decrypted_login()` in `custom_components/syr_connect/response_parser.py` raises `SyrConnectAuthError`, which triggers the re-authentication flow. The server's `<msg v="…">` text is appended to the error message for the log, and the decrypted content is logged at debug level (it contains no session token).
  - Every other unexpected login response (no XML, e.g. a maintenance page, no `sc>api`, no projects) is raised as `SyrConnectConnectionError` by `SyrConnectXmlAPI.login()` in `custom_components/syr_connect/api_xml.py`: it is only logged, entities keep their last values, and no re-authentication is requested.
  - Test: `test_parse_decrypted_login_rejected_credentials_response` in `tests/test_response_parser.py` uses both responses above.

### 4. Invalid or expired session token returns HTTP 200 with a message

- Tentatively be considered part of the design, but it is not ideal.
- Description: Requests with an invalid or expired session token (`<us ug="…"/>`) are not answered with an HTTP error. The server returns HTTP 200 with no data, only a `<msg>` element. Observed (2026-10-18) for `GetProjectDeviceCollections` and `GetDeviceCollectionStatus` with a modified token, a random UUID and an empty token, always identical:

  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <sc>
    <msg v="Der Access-Token ist ungültig oder abgelaufen. Bitte loggen Sie sich erneut ein." hl="Ungültiger Token !" mtid="1" />
    <cs v="2B20" />
  </sc>
  ```

  The texts are always German: sending `lng`/`reg` (login), `Accept-Language` and the locale in the app version string as `en-US` or `en-GB` makes no difference. The lifetime of a session is unknown.
- Impact: The HTTP status cannot distinguish a rejected token from a successful request. Without special handling, the response looks like an incomplete answer (no `prs`/`dvs`), and the session would never be renewed.
- Mitigation in this project:
  - The response parser recognizes the message by `mtid="1"` (language-independent) and raises `SyrConnectSessionExpiredError` (a `SyrConnectConnectionError`): `_raise_if_session_expired()` / `raise_if_session_expired()` in `custom_components/syr_connect/response_parser.py`.
  - `SyrConnectXmlAPI._post_with_session()` in `custom_components/syr_connect/api_xml.py` then logs in again and repeats the request once with the new token. Parallel requests that get the rejection at the same time share one login (`_relogin()`, guarded by a lock). If the new token is rejected as well, the error is handled like any other connection error: logged, entities keep their last values.
  - There is no client-side session expiry: a new login only happens when the server rejects the token.
  - Fixture: `tests/fixtures/xml/SyrTestDevice_InvalidSessionResponse.xml`. Tests: `test_invalid_token_response_raises_session_expired` in `tests/test_response_parser.py`, `test_rejected_token_relogs_in_and_retries_once` and `test_rejected_token_twice_raises_session_expired` in `tests/test_api_xml.py`.

## References

- Parser: [custom_components/syr_connect/response_parser.py](custom_components/syr_connect/response_parser.py)
