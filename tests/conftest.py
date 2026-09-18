"""Shared pytest setup: the kind marker, the tag contract, and a safe HOME.

Three axes classify every test here. `kind` is applied below from the
directory a test sits in, so no test repeats its own path. `cost` and `venue`
are written on the test, and a test that carries neither is a collection
error rather than a test that silently never runs.

The fixtures exist for one reason: this suite drives code whose job is
deleting files next to `auth.json`. Nothing here may touch the real home
directory, and `tmp_home` is how a test says so.
"""

from __future__ import annotations

import os
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

KINDS = frozenset({"unit", "integration", "e2e", "meta"})
COSTS = frozenset({"fast", "slow"})
VENUES = frozenset({"local", "ci"})


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Tag each test with its kind, and refuse a test that claims no budget."""
    untagged: list[str] = []

    for item in items:
        path = pathlib.Path(str(item.fspath)).resolve()
        try:
            kind = path.relative_to(TESTS).parts[0]
        except ValueError:
            kind = ""
        if kind in KINDS:
            item.add_marker(getattr(pytest.mark, kind))

        marks = {mark.name for mark in item.iter_markers()}
        missing = []
        if not marks & COSTS:
            missing.append("a cost marker (fast or slow)")
        if not marks & VENUES:
            missing.append("a venue marker (local or ci)")
        if missing:
            untagged.append(f"{item.nodeid}: needs {' and '.join(missing)}")

    if untagged:
        raise pytest.UsageError(
            "every test carries a cost and a venue, or it never runs:\n  "
            + "\n  ".join(untagged)
        )


@pytest.fixture
def repo_root() -> pathlib.Path:
    """The source tree under test."""
    return ROOT


@pytest.fixture
def vocab() -> dict[str, frozenset[str]]:
    """The tag vocabulary, for the meta test that keeps four files in step.

    A fixture rather than an import: pytest puts this file on the path at
    run time, but no static tool can see that, so importing it from a test
    reads as unresolved everywhere else.
    """
    return {"kind": KINDS, "cost": COSTS, "venue": VENUES}


@pytest.fixture
def tmp_home(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """A throwaway ``$HOME`` with the live agent directory inside it.

    Returns the home directory. ``PI_CODING_AGENT_DIR`` points at
    ``<home>/.pi/agent`` and is not created, because several tests need to
    watch what creates it.

    The assertion is not defensive noise. A bug in this fixture would point
    the prune engine at the operator's real credentials.
    """
    home = tmp_path / "home"
    dest = home / ".pi" / "agent"
    home.mkdir()

    real_home = pathlib.Path(os.path.expanduser("~")).resolve()
    resolved = home.resolve()
    assert real_home not in resolved.parents and resolved != real_home, (
        f"tmp_home landed inside the real home directory: {resolved}"
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(dest))
    monkeypatch.delenv("PI_CONFIG_PRUNE", raising=False)
    monkeypatch.delenv("PI_CONFIG_RUN_MANIFEST", raising=False)
    return home
