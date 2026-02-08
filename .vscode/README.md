# VS Code Configuration

This directory contains VS Code configuration files for the SYR Connect custom integration development.

## Files

### `settings.default.jsonc`

Default workspace settings for the project. These settings are shared across the team.

**Important:** If you need personal settings that differ from the defaults:

1. Copy `settings.default.jsonc` to `settings.json`
2. Make your personal changes in `settings.json`
3. `settings.json` is gitignored and won't be committed

### `tasks.json`

Defines tasks for common development operations:

- **Pytest** - Run all tests
- **Pytest (changed tests only)** - Run only changed tests (requires pytest-picked)
- **Pytest with Coverage** - Run tests with coverage report
- **Ruff Check** - Lint code
- **Ruff Format** - Format code
- **Mypy Type Check** - Type checking
- **Install Dev Requirements** - Install development dependencies
- **Pre-commit Run All** - Run all pre-commit hooks

Run tasks via: `Terminal > Run Task...` or `Ctrl+Shift+P > Tasks: Run Task`

### `launch.json`

Debug configurations:

- **Debug Current Test File** - Debug the currently open test file
- **Debug All Tests** - Debug all tests
- **Debug Changed Tests** - Debug only changed tests
- **Attach to Local/Remote Home Assistant** - Attach debugger to running HA instance

### `extensions.json`

Recommended extensions for this project:

- Ruff (charliermarsh.ruff) - Python linting and formatting
- Prettier (esbenp.prettier-vscode) - JSON/YAML formatting
- Python (ms-python.python) - Python language support
- Mypy Type Checker (ms-python.mypy-type-checker) - Type checking

VS Code will prompt you to install these when you open the workspace.

## Quick Start

1. Install recommended extensions when prompted
2. Select your Python interpreter: `Ctrl+Shift+P > Python: Select Interpreter`
3. Install dev requirements: Run task "Install Dev Requirements"
4. Run tests: `Ctrl+Shift+P > Tasks: Run Task > Pytest`
