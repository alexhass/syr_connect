
# CODE_STYLE.md

## Project-wide Quality Guidelines and Coding Standards

This file defines the mandatory rules for development in the `syr_connect` project (Home Assistant Custom Component, Python).

---

### 1. General Python Standards

- **Type Annotations:**
  - All functions and methods must have type annotations.
  - Use modern union syntax (`str | None` instead of `Optional[str]`).
- **Imports:**
  - Sort imports: standard library, third-party, project modules.
  - No lazy imports (no imports inside functions, except in tests).
- **Naming Conventions:**
  - Modules: `snake_case.py`
  - Classes: `PascalCase`
  - Functions/Methods: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`
  - Private members: `_leading_underscore`
- **Error Handling:**
  - Use specific exceptions, no bare `except:` blocks.
  - Always raise exceptions with context.
- **Formatting:**
  - Maximum line length: 120 characters.
  - Use `ruff format` and `black` for automatic formatting.
- **Docstrings:**
  - Public classes and methods require docstrings.
  - Docstrings must be short, precise, and end with a period.
  - Do not repeat type information in docstrings.

---

### 2. Home Assistant-Specific Rules

- **Entities:**
  - Sensors, switches, etc. are implemented as separate classes.
  - Entities use the appropriate device and state classes.
  - Icons and units are managed centrally in `const.py`.
- **Configuration:**
  - Configuration options and defaults are maintained in `const.py`.
- **Translations:**
  - All texts and names are managed via the `translations/` files.
- **Tests:**
  - Tests are located in the `tests/` directory and use `pytest`.
  - Aim for >90% test coverage for core logic.
- **Integration:**
  - No Home Assistant-specific imports in models or helpers, only in platform files (`sensor.py`, `binary_sensor.py`, etc.).

---

### 3. Git and Workflow Rules

- **Commits:**
  - Use descriptive commit messages (e.g., `fix(sensor): Correct icon name`).
  - Use feature and bugfix branches, never push directly to `main`.
- **Pre-Commit Hooks:**
  - Before every commit: run `ruff`, `mypy`, `pytest`, and optionally `black`.
- **Changelog:**
  - Changes to public APIs must be documented in the changelog.

---

### 4. Clean Code Policy

- No legacy compatibility layers, aliases, or deprecated elements after refactoring.
- Migrations must be complete and consistent.
- After refactoring: no TODO or FIXME comments in the code.

---

### 5. Example of Correct Style

```python
from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from typing import TYPE_CHECKING

class WaterSensor(SensorEntity):
    """Sensor for water consumption."""

    def __init__(self, name: str, unit: str) -> None:
        self._attr_name = name
        self._attr_unit_of_measurement = unit

    @property
    def state(self) -> float | None:
        """Return the current value."""
        # ...
```

---

### 6. Tools

- **Formatting:** `ruff format`, `black`
- **Linting:** `ruff`, `pylint`
- **Type Checking:** `mypy`
- **Tests:** `pytest`

---

### 7. Language

- Code comments, docstrings, and documentation must be written in English.

---

**This file is binding for all contributions to this project. Changes to the rules require review.**
