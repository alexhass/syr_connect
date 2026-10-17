---
description: Running and writing tests for syr_connect
applyTo: "tests/**/*.py"
---

# Tests

- Pytest needs `fcntl` and does not run on Windows. Use WSL or the "Pytest (WSL)" task, never a Windows virtualenv.
- `MagicMock(spec=SyrConnectDataUpdateCoordinator)` exposes attributes without a default as random mocks. Set `entry_id` explicitly when the test depends on registry removal. `tests/conftest.py::create_mock_coordinator` sets it to `None`.
- Hand-written coordinator stand-ins (`class Dummy*Coord`) need `entry_id = None`.
- When adding a coordinator attribute used in registry removal, grep the tests for `async_remove.assert_called` and `.async_remove.called`.
- Select entities for `getPRF` and `getSRO` have no `_sensor_key`. Identify them with `isinstance(e, SyrConnectPrfSelect)` / `SyrConnectRotationSelect`.
- Do not tie generic detection tests to real `models.py` entries. Patch `models.MODEL_SIGNATURES` with a synthetic signature.
- After editing production code or tests that a revert touched, read both the code and its tests again before changing either.
