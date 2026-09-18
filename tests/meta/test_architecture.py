"""The shape of `scripts/pi_config/`, enforced rather than described.

A package splits cleanly once and then drifts, because nothing stops the
next edit from importing sideways or upward. These tests are what stops it.

The rule is one direction. A module may import from a strictly lower layer
and never from its own or a higher one, which makes cycles impossible by
construction rather than by review.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]

# Lower numbers are closer to the filesystem. A module may import anything
# with a strictly smaller number.
LAYERS = {
    "paths": 0,
    "fsx": 0,
    "gitx": 0,
    "pins": 1,
    "manifest": 1,
    "sidecars": 2,
    "prune": 2,
    "status": 2,
    "landing": 3,
    "trees": 3,
    "__main__": 4,
}

# A module past this wants splitting. It is a pressure signal, not a law of
# nature: raise it deliberately, in a commit that says why.
MAX_LINES = 300


def package(repo_root: pathlib.Path) -> pathlib.Path:
    return repo_root / "scripts" / "pi_config"


def modules(repo_root: pathlib.Path) -> dict[str, pathlib.Path]:
    return {
        path.stem: path
        for path in sorted(package(repo_root).glob("*.py"))
        if path.stem != "__init__"
    }


def local_imports(path: pathlib.Path) -> set[str]:
    """The sibling modules this file imports, from `from .x import y`."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module:
            found.add(node.module)
    return found


def test_every_module_has_a_declared_layer(repo_root: pathlib.Path) -> None:
    """A new module must be placed, not left to find its own level."""
    assert set(modules(repo_root)) == set(LAYERS)


def test_no_module_imports_its_own_layer_or_higher(
    repo_root: pathlib.Path,
) -> None:
    offences = []
    for name, path in modules(repo_root).items():
        for imported in local_imports(path):
            if LAYERS[imported] >= LAYERS[name]:
                offences.append(
                    f"{name} (layer {LAYERS[name]}) imports "
                    f"{imported} (layer {LAYERS[imported]})"
                )
    assert offences == []


def test_the_import_graph_has_no_cycles(repo_root: pathlib.Path) -> None:
    """Implied by the layering, and asserted directly so it survives a
    change to the layer map that looks harmless."""
    graph = {name: local_imports(path) for name, path in modules(repo_root).items()}
    seen: set[str] = set()
    stack: list[str] = []

    def walk(node: str) -> None:
        if node in stack:
            raise AssertionError(f"import cycle: {' -> '.join([*stack, node])}")
        if node in seen:
            return
        stack.append(node)
        for nxt in sorted(graph.get(node, ())):
            walk(nxt)
        stack.pop()
        seen.add(node)

    for name in sorted(graph):
        walk(name)


def test_no_module_is_over_the_size_budget(repo_root: pathlib.Path) -> None:
    oversized = {
        name: len(path.read_text().splitlines())
        for name, path in modules(repo_root).items()
        if len(path.read_text().splitlines()) > MAX_LINES
    }
    assert oversized == {}, f"over {MAX_LINES} lines: {oversized}"


def test_every_module_has_a_test_module(repo_root: pathlib.Path) -> None:
    """A module nobody tests is a module nobody can refactor.

    Unit or integration, whichever suits the module. `landing` writes real
    files, so its tests live in integration.
    """
    tested = {
        path.stem.removeprefix("test_")
        for kind in ("unit", "integration")
        for path in (repo_root / "tests" / kind).glob("test_*.py")
    }
    # __main__ is the argument table. The end-to-end suite drives it as a
    # command line, which is the only way it is ever used.
    expected = set(LAYERS) - {"__main__"}
    assert expected <= tested, f"no unit tests for: {sorted(expected - tested)}"


def test_the_facade_exports_every_public_name(repo_root: pathlib.Path) -> None:
    """`pi_config.x` must keep working for every x a module defines.

    Callers and tests reach names through the package, so a module that
    grows a public function without exporting it splits the surface in two.
    """
    facade = ast.parse((package(repo_root) / "__init__.py").read_text())
    exported = {
        alias.name
        for node in ast.walk(facade)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    missing: list[str] = []
    for name, path in modules(repo_root).items():
        if name == "__main__":
            continue
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                if node.name not in exported:
                    missing.append(f"{name}.{node.name}")
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id.isupper()
                        and target.id not in exported
                    ):
                        missing.append(f"{name}.{target.id}")

    assert missing == [], f"defined but not re-exported: {sorted(missing)}"
