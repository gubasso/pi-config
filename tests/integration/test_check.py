"""The source-tree contract a pre-commit hook runs.

`check` is the subset of doctor that needs no host landing, plus the one
thing only git can answer: whether a secret is tracked. `.gitignore` cannot
catch a `git add -f`, and this can.
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
    agent = root / "home" / ".pi" / "agent"
    (agent / "prompts").mkdir(parents=True)
    (agent / "extensions").mkdir()
    (root / "home" / ".pi" / "lsp-client.json").write_text("{}")

    for name in pi_config.REQUIRED_META:
        (root / name).write_text("x\n")
    (root / ".gitignore").write_text(
        "\n".join(pi_config.REQUIRED_IGNORES) + "\n/home/.pi/agent/models-store.json\n"
    )
    (agent / "AGENTS.md").write_text("# payload\n")
    (agent / "prompts" / "review.md").write_text("# review\n")
    (agent / "extensions" / "worktree-guard.ts").write_text("// guard\n")
    (agent / "settings.json").write_text('{"packages":[]}')

    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "x"], cwd=root, check=True)
    return root


def force_track(clone: pathlib.Path, rel: str, body: str = "{}") -> None:
    """Commit a path .gitignore covers, the way `git add -f` would."""
    path = clone / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    subprocess.run(["git", "add", "-f", rel], cwd=clone, check=True)


class TestCheck:
    def test_passes_a_clean_tree(self, clone: pathlib.Path) -> None:
        pi_config.check(str(clone), [], [])

    @pytest.mark.parametrize("rel", pi_config.FORBIDDEN_PATHS)
    def test_refuses_a_tracked_secret(self, clone: pathlib.Path, rel: str) -> None:
        force_track(clone, rel)

        with pytest.raises(SystemExit, match="tracked secret"):
            pi_config.check(str(clone), [], [])

    @pytest.mark.parametrize("prefix", pi_config.FORBIDDEN_PREFIXES)
    def test_refuses_a_tracked_install_tree_or_transcript(
        self, clone: pathlib.Path, prefix: str
    ) -> None:
        """Vendoring these would put a package tree or a session into git."""
        force_track(clone, prefix + "thing.json")

        with pytest.raises(SystemExit, match="tracked secret or install tree"):
            pi_config.check(str(clone), [], [])

    def test_still_proves_the_source_tree(self, clone: pathlib.Path) -> None:
        """check is doctor's source half plus the git question, not instead."""
        (clone / "SPEC.md").unlink()

        with pytest.raises(SystemExit, match="missing"):
            pi_config.check(str(clone), [], [])

    def test_a_path_that_merely_shares_a_prefix_is_fine(
        self, clone: pathlib.Path
    ) -> None:
        """`npm-notes.md` is not the `npm/` tree."""
        force_track(clone, "home/.pi/agent/npm-notes.md", "# notes\n")
        pi_config.check(str(clone), [], [])
