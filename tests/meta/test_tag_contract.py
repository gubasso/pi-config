"""The three axes are declared in four files. They must say the same words.

`pytest.ini`, `tests/conftest.py`, `scripts/run-tests.sh`, and
`tests/helpers/tags.ts` each name the tag vocabulary. Nothing made them agree
before this test, and a tag that exists in one file and not another is a test
that silently never runs.
"""

from __future__ import annotations

import configparser
import pathlib
import re

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]

Vocab = dict[str, frozenset[str]]


def only_match(pattern: str, text: str, group: int = 1) -> str:
    """The one capture the pattern must find, or a readable failure."""
    found = re.search(pattern, text, re.M)
    assert found is not None, f"no match for {pattern!r}"
    return found.group(group)


def ini(repo_root: pathlib.Path) -> configparser.SectionProxy:
    parser = configparser.ConfigParser()
    parser.read(repo_root / "pytest.ini")
    return parser["pytest"]


def test_pytest_ini_declares_every_axis(repo_root: pathlib.Path, vocab: Vocab) -> None:
    declared = {
        line.split(":", 1)[0].strip()
        for line in ini(repo_root)["markers"].strip().splitlines()
    }
    assert declared == set().union(*vocab.values())


def test_pytest_ini_is_strict_about_markers(repo_root: pathlib.Path) -> None:
    """Without --strict-markers a typo is a test that never runs."""
    assert "--strict-markers" in ini(repo_root)["addopts"]


def test_runner_knows_the_same_costs(repo_root: pathlib.Path, vocab: Vocab) -> None:
    runner = (repo_root / "scripts" / "run-tests.sh").read_text()
    # shfmt puts a top-level case arm at column zero, so do not require
    # indentation here. The arm is the declaration; its column is not.
    budgets = dict(re.findall(r"^\s*(\w+)\) costs=\(([\w ]+)\)", runner, re.M))

    assert set(budgets) == {"fast", "slow", "all"}
    assert {cost for value in budgets.values() for cost in value.split()} == vocab[
        "cost"
    ]
    assert set(budgets["all"].split()) == vocab["cost"], "all must mean every cost"


def test_runner_knows_the_same_venues(repo_root: pathlib.Path, vocab: Vocab) -> None:
    runner = (repo_root / "scripts" / "run-tests.sh").read_text()
    default = only_match(r"^venue=(\w+)$", runner)
    under_ci = only_match(r"^\s+venue=(\w+)$", runner)

    assert {default, under_ci} == vocab["venue"]
    assert default == "local", "a plain run is a local run"


def test_vitest_helper_knows_the_same_axes(
    repo_root: pathlib.Path, vocab: Vocab
) -> None:
    helper = (repo_root / "tests" / "helpers" / "tags.ts").read_text()

    def union(name: str) -> set[str]:
        return set(
            re.findall(
                r'"(\w+)"', only_match(rf"export type {name} = ([^;]+);", helper)
            )
        )

    assert union("Cost") == vocab["cost"]
    assert union("Venue") == vocab["venue"]


def test_every_directory_under_tests_is_a_kind(
    repo_root: pathlib.Path, vocab: Vocab
) -> None:
    present = {
        entry.name
        for entry in (repo_root / "tests").iterdir()
        if entry.is_dir() and not entry.name.startswith((".", "__"))
    }
    assert present - {"helpers"} <= vocab["kind"]
