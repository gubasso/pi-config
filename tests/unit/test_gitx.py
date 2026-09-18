"""The three questions this engine asks git.

`git_ignored` is how doctor proves a live-only sidecar can never be
committed. `git_tracked` is how it proves a copy or symlink sidecar is.
`git_head_bytes` supplies the base for the 3-way merge that keeps a
hardlinked sidecar in step.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


@pytest.fixture
def clone(tmp_path: pathlib.Path, tmp_home: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "clone"
    (root / "home" / ".pi" / "agent").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / ".gitignore").write_text("/home/.pi/agent/auth.json\n")
    return root


def commit(clone: pathlib.Path) -> None:
    subprocess.run(["git", "add", "-A"], cwd=clone, check=True)
    subprocess.run(["git", "commit", "-qm", "x"], cwd=clone, check=True)


class TestGitIgnored:
    def test_reports_a_path_gitignore_covers(self, clone: pathlib.Path) -> None:
        rel = pi_config.sidecar_repo_path(".pi/agent/auth.json")
        assert pi_config.git_ignored(str(clone), rel)

    def test_reports_a_path_it_does_not(self, clone: pathlib.Path) -> None:
        rel = pi_config.sidecar_repo_path(".pi/agent/settings.json")
        assert not pi_config.git_ignored(str(clone), rel)

    def test_answers_for_a_file_that_does_not_exist(self, clone: pathlib.Path) -> None:
        """--no-index is what makes this a question about the rule."""
        rel = pi_config.sidecar_repo_path(".pi/agent/auth.json")
        assert not (clone / rel).exists()
        assert pi_config.git_ignored(str(clone), rel)


class TestGitTracked:
    def test_reports_a_committed_file(self, clone: pathlib.Path) -> None:
        rel = pi_config.sidecar_repo_path(".pi/agent/settings.json")
        (clone / rel).write_text("{}")
        commit(clone)

        assert pi_config.git_tracked(str(clone), rel)

    def test_reports_an_untracked_file(self, clone: pathlib.Path) -> None:
        rel = pi_config.sidecar_repo_path(".pi/agent/settings.json")
        (clone / rel).write_text("{}")

        assert not pi_config.git_tracked(str(clone), rel)


class TestGitHeadBytes:
    def test_returns_the_committed_content(self, clone: pathlib.Path) -> None:
        rel = pi_config.sidecar_repo_path(".pi/agent/thing.json")
        (clone / rel).write_text('{"a":1}')
        commit(clone)
        (clone / rel).write_text('{"a":2}')

        assert pi_config.git_head_bytes(str(clone), rel) == b'{"a":1}'

    def test_returns_none_for_a_file_absent_from_head(
        self, clone: pathlib.Path
    ) -> None:
        """A newly authored sidecar has no base, and the merge says so."""
        rel = pi_config.sidecar_repo_path(".pi/agent/thing.json")
        (clone / rel).write_text("{}")

        assert pi_config.git_head_bytes(str(clone), rel) is None

    def test_returns_none_in_a_repository_with_no_commits(
        self, clone: pathlib.Path
    ) -> None:
        rel = pi_config.sidecar_repo_path(".pi/agent/thing.json")
        assert pi_config.git_head_bytes(str(clone), rel) is None
