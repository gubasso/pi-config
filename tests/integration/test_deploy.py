"""Landing the payload: what deploy copies, links, and refuses.

This was three hundred lines of bash inside the justfile, and the only way
to drive it was a whole deploy. The cases here are the ones that were
unreachable then: one landing step at a time, against real files in a
throwaway tree.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


@pytest.fixture
def clone(tmp_path: pathlib.Path, tmp_home: pathlib.Path) -> pathlib.Path:
    """A source tree deploy will accept.

    Deploy proves the clone before it writes or deletes anything, so a
    fixture carrying only the payload is no longer enough.
    """
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
    (agent / "AGENTS.md").write_text("# payload rules\n")
    (agent / "prompts" / "review.md").write_text("# review\n")
    (agent / "extensions" / "worktree-guard.ts").write_text("// guard\n")
    (agent / "settings.json").write_text('{"packages":[]}')

    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


@pytest.fixture
def dest(tmp_home: pathlib.Path) -> pathlib.Path:
    return tmp_home / ".pi" / "agent"


@pytest.fixture(autouse=True)
def fresh_record() -> None:
    pi_config.reset_landed()


class TestLandPayload:
    def test_copies_the_static_payload(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        dest.mkdir(parents=True)
        pi_config.land_payload(str(clone), str(dest))

        assert (dest / "AGENTS.md").read_text() == "# payload rules\n"
        assert (dest / "prompts" / "review.md").read_text() == "# review\n"
        assert not (dest / "AGENTS.md").is_symlink()

    def test_links_what_the_runtime_writes(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        dest.mkdir(parents=True)
        pi_config.land_payload(str(clone), str(dest))

        landed = dest / "settings.json"
        assert landed.is_symlink()
        assert os.path.realpath(landed) == os.path.realpath(
            clone / "home" / ".pi" / "agent" / "settings.json"
        )

    def test_skips_an_optional_file_that_is_absent(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        dest.mkdir(parents=True)
        pi_config.land_payload(str(clone), str(dest))

        assert not (dest / "APPEND_SYSTEM.md").exists()
        assert not (dest / "keybindings.json").exists()

    def test_lands_an_optional_file_that_is_present(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        agent = clone / "home" / ".pi" / "agent"
        (agent / "APPEND_SYSTEM.md").write_text("# appended\n")
        (agent / "keybindings.json").write_text("{}")
        dest.mkdir(parents=True)

        pi_config.land_payload(str(clone), str(dest))

        assert (dest / "APPEND_SYSTEM.md").exists()
        assert (dest / "keybindings.json").is_symlink()

    def test_records_every_path_it_lands(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        dest.mkdir(parents=True)
        pi_config.land_payload(str(clone), str(dest))

        recorded = dict(pi_config.landed())
        assert recorded[str(dest / "AGENTS.md")] == "copy"
        assert recorded[str(dest / "settings.json")] == "symlink"
        assert recorded[str(dest / "prompts")] == "dir"


class TestCopyDirFiles:
    def test_copies_one_level_only(self, tmp_path: pathlib.Path) -> None:
        """Pi discovers a prompt at the top of its directory.

        A subdirectory here would land nowhere and be noticed by nobody, so
        deploy does not pretend to handle one.
        """
        source = tmp_path / "prompts"
        (source / "nested").mkdir(parents=True)
        (source / "a.md").write_text("a")
        (source / "nested" / "b.md").write_text("b")
        target = tmp_path / "dest" / "prompts"

        pi_config.copy_dir_files(str(source), str(target))

        assert (target / "a.md").exists()
        assert not (target / "nested").exists()

    def test_replaces_a_symlinked_destination_with_a_directory(
        self, tmp_path: pathlib.Path
    ) -> None:
        source = tmp_path / "prompts"
        source.mkdir()
        (source / "a.md").write_text("a")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        target = tmp_path / "dest" / "prompts"
        target.parent.mkdir()
        target.symlink_to(elsewhere)

        pi_config.copy_dir_files(str(source), str(target))

        assert target.is_dir()
        assert not target.is_symlink()


class TestLinkTracked:
    def test_replaces_an_existing_file(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "settings.json"
        source.write_text("{}")
        target = tmp_path / "dest" / "settings.json"
        target.parent.mkdir()
        target.write_text("stale")

        pi_config.link_tracked(str(source), str(target))

        assert target.is_symlink()

    def test_refuses_to_replace_a_directory(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "settings.json"
        source.write_text("{}")
        target = tmp_path / "dest" / "settings.json"
        target.mkdir(parents=True)

        with pytest.raises(SystemExit, match="refusing to replace directory"):
            pi_config.link_tracked(str(source), str(target))

    def test_refuses_a_destination_home_manager_owns(
        self, tmp_path: pathlib.Path
    ) -> None:
        source = tmp_path / "settings.json"
        source.write_text("{}")
        target = tmp_path / "dest" / "settings.json"
        target.parent.mkdir()
        target.symlink_to("/nix/store/does-not-exist-settings")

        with pytest.raises(SystemExit, match="Home Manager"):
            pi_config.link_tracked(str(source), str(target))


class TestDeploy:
    def test_refuses_before_writing_anything_when_a_root_is_a_symlink(
        self, clone: pathlib.Path, dest: pathlib.Path, tmp_home: pathlib.Path
    ) -> None:
        """The guard runs first, so a swapped root cannot redirect a landing."""
        elsewhere = tmp_home.parent / "elsewhere"
        elsewhere.mkdir()
        (tmp_home / ".pi").symlink_to(elsewhere)

        with pytest.raises(SystemExit, match="symlink"):
            pi_config.deploy(str(clone), str(dest), [], [])

        assert not (elsewhere / "agent").exists()

    def test_refuses_a_destination_home_manager_owns(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        dest.mkdir(parents=True)
        (dest / "AGENTS.md").symlink_to("/nix/store/does-not-exist-agents-md")

        with pytest.raises(SystemExit, match="Home Manager"):
            pi_config.deploy(str(clone), str(dest), [], [])

    def test_creates_the_destination_and_returns_it_resolved(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        got = pi_config.deploy(str(clone), str(dest), [], [])

        assert got == os.path.realpath(dest)
        assert (dest / "AGENTS.md").exists()

    def test_starts_each_run_with_an_empty_record(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        """A landing carried over from a previous run would hide a prune."""
        pi_config.record("copy", str(dest / "from-a-previous-run.md"))

        pi_config.deploy(str(clone), str(dest), [], [])

        recorded = {path for path, _ in pi_config.landed()}
        assert str(dest / "from-a-previous-run.md") not in recorded


class TestDeployPreflight:
    """Nothing is written or deleted until the clone has been proved.

    Deploy converges, so it deletes. Proving the source only afterwards
    means a tree missing a required payload file has already had the live
    copy pruned by the time doctor says so.
    """

    def test_a_missing_required_payload_file_leaves_the_destination_alone(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        landed = pathlib.Path(pi_config.deploy(str(clone), str(dest), [], []))
        assert (landed / "prompts" / "review.md").exists()

        (clone / "home" / ".pi" / "agent" / "prompts" / "review.md").unlink()

        with pytest.raises(SystemExit, match="missing"):
            pi_config.deploy(str(clone), str(dest), [], [])

        # The run failed, and it failed before pruning what it could no
        # longer land.
        assert (landed / "prompts" / "review.md").exists()

    def test_a_destination_inside_the_clone_is_never_written_to(
        self, clone: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The clone is source. Deploy onto it would land onto itself."""
        inside = clone / "home" / ".pi" / "agent"
        monkeypatch.setenv("PI_CODING_AGENT_DIR", str(inside))
        before = sorted(p.name for p in inside.iterdir())

        with pytest.raises(SystemExit, match="inside this clone"):
            pi_config.deploy(str(clone), str(inside), [], [])

        assert sorted(p.name for p in inside.iterdir()) == before

    def test_the_guard_does_not_depend_on_the_variable_being_set(
        self, clone: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The dangerous case is the one where nobody set the variable.

        The justfile expands `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}` in the
        shell and never exports it. A clone sitting at that default therefore
        reached the guard with the variable unset, and an earlier guard that
        read the environment let it straight through.
        """
        monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
        inside = clone / "home" / ".pi" / "agent"
        before = sorted(p.name for p in inside.iterdir())

        with pytest.raises(SystemExit, match="inside this clone"):
            pi_config.deploy(str(clone), str(inside), [], [])

        assert sorted(p.name for p in inside.iterdir()) == before

    def test_the_clone_root_is_refused_as_a_destination(
        self, clone: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Landing onto the clone root would overwrite its own AGENTS.md."""
        monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
        rules = (clone / "AGENTS.md").read_text()

        with pytest.raises(SystemExit, match="inside this clone"):
            pi_config.deploy(str(clone), str(clone), [], [])

        assert (clone / "AGENTS.md").read_text() == rules

    def test_a_symlinked_payload_destination_does_not_truncate_its_target(
        self, clone: pathlib.Path, dest: pathlib.Path, tmp_home: pathlib.Path
    ) -> None:
        """The end-to-end form of the copy_regular regression."""
        dest.mkdir(parents=True)
        victim = dest / "auth.json"
        victim.write_text('{"token":"secret"}')
        (dest / "AGENTS.md").symlink_to(victim)

        pi_config.deploy(str(clone), str(dest), [], [])

        assert victim.read_text() == '{"token":"secret"}'
        assert (dest / "AGENTS.md").read_text() == "# payload rules\n"
