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
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

# The operator's real home, captured at import time.
#
# `tmp_home` replaces $HOME, so after it runs `expanduser("~")` reports the
# throwaway one. Anything asking "is this the real home?" later would compare
# the throwaway against itself and always agree. tests/helpers/common.bash
# captures the same value for the same reason.
REAL_HOME = pathlib.Path(os.path.expanduser("~")).resolve()

# The engine, imported rather than shelled out to. The justfile puts the same
# directory on PYTHONPATH for `python3 -m pi_config`, so a test drives the
# module a recipe runs and not a copy of it. pyrightconfig.json repeats the
# path for the editor, which cannot see this line.
sys.path.insert(0, str(ROOT / "scripts"))

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


# Everything `git` exports to a hook it runs.
#
# This is the most dangerous inheritance in the suite. A pre-commit hook runs
# inside `git commit`, which exports GIT_INDEX_FILE and GIT_DIR pointing at
# the real repository. A test that then runs `git add` in a throwaway clone
# writes those files through to the real index instead: the repository's
# staged state is replaced by the throwaway's, so every real path reads as
# deleted and whatever the test created reads as added.
#
# That is not a hypothesis. It is what happened here, twice, and the stray
# path left in the index named the fixture that caused it.
GIT_HOOK_ENV = (
    "GIT_INDEX_FILE",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_INTERNAL_GETTEXT_TEST_FALLBACKS",
)


@pytest.fixture(autouse=True)
def git_is_not_inherited(monkeypatch: pytest.MonkeyPatch) -> None:
    """Detach every test from the repository git may have handed us.

    Autouse and unconditional, because the failure is silent and the damage
    lands on the operator's real index rather than on the test.
    """
    for name in GIT_HOOK_ENV:
        monkeypatch.delenv(name, raising=False)


def payload_listing() -> set[str]:
    """Every path under the tracked payload, as names only."""
    payload = ROOT / "home"
    return {str(path.relative_to(ROOT)) for path in payload.rglob("*") if path.exists()}


@pytest.fixture(autouse=True)
def payload_is_read_only():
    """Fail any test that writes into this repository's own payload.

    The engine under test lands files, and every test is supposed to land
    them into a throwaway tree. A test that passes the real source tree
    instead writes into `home/`, which then gets picked up by the next
    `git add -A` and staged as a real change. That already happened once
    here, and nothing reported it.

    Checking names rather than contents keeps this cheap: the payload is a
    handful of files, and a stray landing always adds a path.
    """
    before = payload_listing()
    yield
    after = payload_listing()
    assert after == before, (
        "a test wrote into the repository payload: "
        f"added {sorted(after - before)}, removed {sorted(before - after)}"
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

    resolved = home.resolve()
    assert REAL_HOME not in resolved.parents and resolved != REAL_HOME, (
        f"tmp_home landed inside the real home directory: {resolved}"
    )

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(dest))
    monkeypatch.delenv("PI_CONFIG_PRUNE", raising=False)
    monkeypatch.delenv("PI_CONFIG_RUN_MANIFEST", raising=False)

    # git reads its global config from $HOME, which no longer exists as far
    # as the operator's settings are concerned. Without this, a fixture that
    # commits fails on a configured hooksPath that now resolves under the
    # throwaway home.
    empty = home / "gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "pi-config tests")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "tests@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "pi-config tests")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "tests@example.invalid")
    return home
