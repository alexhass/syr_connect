"""Tests that aiosyrconnect stays a library of its own, independent of Home Assistant."""

import ast
from pathlib import Path
import sys

import pytest

from custom_components.syr_connect import aiosyrconnect

_SYR_CONNECT_TEST_LIBRARY_DIR = Path(aiosyrconnect.__file__).parent
_SYR_CONNECT_TEST_LIBRARY_TESTS_DIR = Path(__file__).parent
_SYR_CONNECT_TEST_LIBRARY_MODULE = "custom_components.syr_connect.aiosyrconnect"

# Distribution that provides each third-party module the library imports
_SYR_CONNECT_TEST_LIBRARY_DISTRIBUTIONS = {
    "aiohttp": "aiohttp",
    "Cryptodome": "pycryptodomex",
    "defusedxml": "defusedxml",
    "yarl": "yarl",
}


def _imports(path: Path) -> list[ast.Import | ast.ImportFrom]:
    """Return every import statement of a module, also the ones inside functions."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom)
    ]


def _imported_modules(node: ast.Import | ast.ImportFrom) -> list[str]:
    """Return the absolute module names of an import statement.

    `from package import module` counts as the module, so that
    `from custom_components.syr_connect import aiosyrconnect` is the library.
    """
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if node.level > 0:
        return []
    module = node.module or ""
    if module == "custom_components.syr_connect":
        return [f"{module}.{alias.name}" for alias in node.names]
    return [module]


@pytest.mark.parametrize(
    "module",
    sorted(_SYR_CONNECT_TEST_LIBRARY_DIR.glob("*.py")),
    ids=lambda path: path.name,
)
def test_library_imports_only_itself(module: Path) -> None:
    """The library imports neither Home Assistant nor a module of the integration.

    Within the library, only modules of the library itself are imported relatively
    (from .models import ...); a relative import from the parent package would reach
    into the integration.
    """
    for node in _imports(module):
        if isinstance(node, ast.ImportFrom) and node.level > 0:
            assert node.level == 1, f"{module.name}:{node.lineno}"
        for name in _imported_modules(node):
            assert not name.startswith("homeassistant"), f"{module.name}:{node.lineno}"
            assert not name.startswith("custom_components"), (
                f"{module.name}:{node.lineno}"
            )


@pytest.mark.parametrize(
    "test_module",
    sorted(_SYR_CONNECT_TEST_LIBRARY_TESTS_DIR.glob("*.py")),
    ids=lambda path: path.name,
)
def test_library_tests_need_only_the_library(test_module: Path) -> None:
    """The tests of the library import neither Home Assistant nor the integration.

    So they test the library alone, as its users see it.
    """
    for node in _imports(test_module):
        for name in _imported_modules(node):
            assert not name.startswith("homeassistant"), (
                f"{test_module.name}:{node.lineno}"
            )
            if name.startswith("custom_components"):
                assert name == _SYR_CONNECT_TEST_LIBRARY_MODULE or name.startswith(
                    f"{_SYR_CONNECT_TEST_LIBRARY_MODULE}."
                ), f"{test_module.name}:{node.lineno}"


def test_public_names_exist() -> None:
    """Every name in __all__ is exported by the package."""
    for name in aiosyrconnect.__all__:
        assert hasattr(aiosyrconnect, name), name


def test_library_is_typed() -> None:
    """The package ships the py.typed marker (PEP 561) for the type checkers of its users."""
    assert (_SYR_CONNECT_TEST_LIBRARY_DIR / "py.typed").is_file()


def test_third_party_imports_are_requirements() -> None:
    """Every third-party module of the library is a requirement listed in README.md.

    So the requirements of the future pyproject.toml are known.
    """
    readme = (_SYR_CONNECT_TEST_LIBRARY_DIR / "README.md").read_text(encoding="utf-8")
    requirements = readme.split("## Requirements", 1)[1].split("\n## ", 1)[0]
    imported = {
        name.split(".")[0]
        for module in _SYR_CONNECT_TEST_LIBRARY_DIR.glob("*.py")
        for node in _imports(module)
        for name in _imported_modules(node)
        if name and name.split(".")[0] not in sys.stdlib_module_names
    }
    assert imported == set(_SYR_CONNECT_TEST_LIBRARY_DISTRIBUTIONS)
    for distribution in _SYR_CONNECT_TEST_LIBRARY_DISTRIBUTIONS.values():
        assert f"`{distribution}`" in requirements, distribution
