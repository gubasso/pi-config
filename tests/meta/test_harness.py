"""Invariants of the test harness itself.

A harness that silently stops isolating is worse than no harness: every test
still passes, and none of them tests what it says. Each case here is a way
that has already happened or could happen without anybody noticing.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest
from conftest import REAL_HOME

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


def test_every_stub_is_executable(repo_root: pathlib.Path) -> None:
    """A stub without the execute bit is skipped by PATH lookup.

    Nothing fails when that happens. The real binary answers instead, the
    tests still pass, and they are no longer testing the stub. This is not
    hypothetical: it is how this suite first ran.
    """
    stubs = repo_root / "tests" / "helpers" / "stubs"
    for stub in sorted(stubs.iterdir()):
        assert os.access(stub, os.X_OK), f"{stub.name} is not executable"


def test_git_records_the_execute_bit_on_every_stub(
    repo_root: pathlib.Path,
) -> None:
    """A local chmod that git does not track is lost on the next clone."""
    listing = subprocess.run(
        ["git", "ls-files", "-s", "tests/helpers/stubs"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    assert listing, "no stubs are tracked"
    for line in listing:
        mode, _, rest = line.partition(" ")
        assert mode == "100755", f"{rest} is tracked as {mode}, want 100755"


def test_the_runner_is_executable(repo_root: pathlib.Path) -> None:
    """pre-commit calls it as a command, not through an interpreter."""
    assert os.access(repo_root / "scripts" / "run-tests.sh", os.X_OK)


def test_tmp_home_is_not_the_real_home(tmp_home: pathlib.Path) -> None:
    """The one assertion the whole suite rests on.

    REAL_HOME comes from conftest, captured at import. Reading expanduser
    here would report the throwaway home this fixture just installed, and
    the comparison would be the throwaway against itself.
    """
    assert tmp_home.resolve() != REAL_HOME
    assert REAL_HOME not in tmp_home.resolve().parents
    assert os.environ["HOME"] == str(tmp_home)


def test_tmp_home_points_the_agent_dir_inside_itself(
    tmp_home: pathlib.Path,
) -> None:
    dest = pathlib.Path(os.environ["PI_CODING_AGENT_DIR"])
    assert tmp_home in dest.parents


def test_tmp_home_clears_the_inherited_deploy_variables(
    tmp_home: pathlib.Path,
) -> None:
    """A leaked run manifest or prune mode would change what a test proves."""
    assert "PI_CONFIG_PRUNE" not in os.environ
    assert "PI_CONFIG_RUN_MANIFEST" not in os.environ


def test_the_bats_helper_captures_the_real_home_before_replacing_it(
    repo_root: pathlib.Path,
) -> None:
    """Resolved after pi_setup, the guard would read the throwaway home.

    It would then pass on anything, including the operator's live agent
    directory.
    """
    helper = (repo_root / "tests" / "helpers" / "common.bash").read_text()
    capture = helper.index('PI_REAL_HOME="$(cd "$HOME"')
    replace = helper.index('export HOME="$BATS_TEST_TMPDIR/home"')
    assert capture < replace


def test_the_payload_guard_notices_a_stray_landing(
    repo_root: pathlib.Path,
) -> None:
    """The guard is autouse, so prove it can actually fail.

    A guard that never fires is indistinguishable from no guard. This writes
    into the payload, confirms the listing changes, and cleans up, so the
    autouse check around this very test still passes.
    """
    from conftest import payload_listing

    stray = repo_root / "home" / ".pi" / "agent" / ".guard-probe"
    before = payload_listing()
    stray.write_text("")
    try:
        assert payload_listing() != before
    finally:
        stray.unlink()
    assert payload_listing() == before


@pytest.mark.parametrize(
    "name", ["GIT_INDEX_FILE", "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"]
)
def test_no_test_inherits_the_callers_git_repository(name: str) -> None:
    """The suite runs from a git hook, and git hands hooks its repository.

    With GIT_INDEX_FILE set, a `git add` anywhere writes the real index.
    The test still passes; the operator's staged state is what breaks.
    """
    assert name not in os.environ


def test_the_bats_helper_detaches_from_git_before_anything_runs(
    repo_root: pathlib.Path,
) -> None:
    helper = (repo_root / "tests" / "helpers" / "common.bash").read_text()
    unset = helper.index("unset GIT_INDEX_FILE")
    first_use = helper.index('export HOME="$BATS_TEST_TMPDIR/home"')
    assert unset < first_use


def test_the_justfile_keeps_the_devshell_on_the_python_path(
    repo_root: pathlib.Path,
) -> None:
    """The justfile adds `scripts/` to PYTHONPATH. It must not replace it.

    The devshell puts every Nix Python package on PYTHONPATH, so a bare
    assignment made `import yaml` fail inside `just test` while a bare
    `pytest` in the same shell passed. The gate is the only path that runs
    under `just`, which is exactly where the breakage hid.
    """
    env = {**os.environ, "PYTHONPATH": "/sentinel/inherited"}
    got = subprocess.run(
        ["just", "--evaluate", "PYTHONPATH"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert got.split(":")[0] == str(repo_root / "scripts")
    assert "/sentinel/inherited" in got.split(":")


def test_the_payload_guard_notices_a_mutation_that_adds_no_path(
    repo_root: pathlib.Path,
) -> None:
    """Overwriting a tracked file changes no name, and is just as stageable.

    The first version of this guard compared names only, so a test could
    rewrite a payload file's bytes, retarget a symlink that still resolved,
    or change a mode, and the guard would agree nothing happened.
    """
    from conftest import payload_listing

    target = repo_root / "home" / ".pi" / "agent" / "AGENTS.md"
    before = payload_listing()
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"\n<!-- guard probe -->\n")
        assert payload_listing() != before
    finally:
        target.write_bytes(original)
    assert payload_listing() == before
