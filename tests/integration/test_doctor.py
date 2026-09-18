"""The proofs: what doctor refuses to pass.

Two halves. The source half needs no landing and is what `just check` runs
from a pre-commit hook. The destination half runs after a deploy.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


@pytest.fixture
def clone(tmp_path: pathlib.Path, tmp_home: pathlib.Path) -> pathlib.Path:
    """A source tree that passes prove_source, so a test can break one thing."""
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

    # prove_source asks git whether the never-commit paths are ignored, so
    # the fixture has to be a repository and not only a directory.
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


@pytest.fixture
def dest(tmp_home: pathlib.Path) -> pathlib.Path:
    return tmp_home / ".pi" / "agent"


class TestProveSource:
    def test_passes_a_complete_tree(self, clone: pathlib.Path) -> None:
        pi_config.prove_source(str(clone), [], [])

    @pytest.mark.parametrize("name", ["SPEC.md", "justfile", "flake.nix"])
    def test_fails_on_a_missing_meta_file(self, clone: pathlib.Path, name: str) -> None:
        (clone / name).unlink()
        with pytest.raises(SystemExit, match="missing"):
            pi_config.prove_source(str(clone), [], [])

    @pytest.mark.parametrize(
        "rel", [".pi/agent/AGENTS.md", ".pi/agent/prompts/review.md"]
    )
    def test_fails_on_a_missing_payload_file(
        self, clone: pathlib.Path, rel: str
    ) -> None:
        (clone / "home" / pathlib.Path(rel)).unlink()
        with pytest.raises(SystemExit, match="missing"):
            pi_config.prove_source(str(clone), [], [])

    def test_fails_when_gitignore_stops_covering_a_runtime_path(
        self, clone: pathlib.Path
    ) -> None:
        kept = [
            line
            for line in (clone / ".gitignore").read_text().splitlines()
            if line != "/home/.pi/agent/auth.json"
        ]
        (clone / ".gitignore").write_text("\n".join(kept) + "\n")

        with pytest.raises(SystemExit, match="gitignore missing"):
            pi_config.prove_source(str(clone), [], [])

    def test_fails_on_settings_that_is_not_json(self, clone: pathlib.Path) -> None:
        (clone / "home" / ".pi" / "agent" / "settings.json").write_text("{not json")
        with pytest.raises(SystemExit, match="not JSON"):
            pi_config.prove_source(str(clone), [], [])

    def test_fails_on_the_override_file_that_was_replaced(
        self, clone: pathlib.Path
    ) -> None:
        (clone / "AGENTS.override.md").write_text("x")
        with pytest.raises(SystemExit, match="AGENTS.override.md"):
            pi_config.prove_source(str(clone), [], [])

    def test_fails_when_the_payload_rules_are_a_store_symlink(
        self, clone: pathlib.Path
    ) -> None:
        """Home Manager owning the source would give the file two writers.

        The link has to resolve. A dangling one fails the required-payload
        check first, which is its own correct answer and the case below.
        """
        payload = clone / "home" / ".pi" / "agent" / "AGENTS.md"
        payload.unlink()
        payload.symlink_to(sys.executable)

        with pytest.raises(SystemExit, match="store symlink"):
            pi_config.prove_source(str(clone), [], [])

    def test_fails_when_a_payload_file_dangles(self, clone: pathlib.Path) -> None:
        payload = clone / "home" / ".pi" / "agent" / "AGENTS.md"
        payload.unlink()
        payload.symlink_to("/nix/store/does-not-exist-agents-md")

        with pytest.raises(SystemExit, match="missing"):
            pi_config.prove_source(str(clone), [], [])


class TestProveDestLocation:
    def test_refuses_a_destination_inside_the_clone(
        self, clone: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The clone is source. Landing onto it would deploy onto itself."""
        inside = clone / "home" / ".pi" / "agent"
        monkeypatch.setenv("PI_CODING_AGENT_DIR", str(inside))

        with pytest.raises(SystemExit, match="inside this clone"):
            pi_config.prove_dest_location(str(clone), str(inside))

    def test_allows_a_destination_elsewhere(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        pi_config.prove_dest_location(str(clone), str(dest))


class TestDoctor:
    def test_source_only_skips_the_destination_entirely(
        self, clone: pathlib.Path, dest: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DOCTOR_SOURCE_ONLY", "1")
        pi_config.doctor(str(clone), str(dest), [], [])

    def test_notes_an_absent_destination_rather_than_failing(
        self, clone: pathlib.Path, dest: pathlib.Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A clone on a machine that has not deployed yet is not broken."""
        pi_config.doctor(str(clone), str(dest), [], [])
        assert "source-only doctor" in capsys.readouterr().out

    def test_proves_a_landed_destination(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        landed = pi_config.deploy(str(clone), str(dest), [])
        pi_config.doctor(str(clone), landed, [], [])

    def test_fails_when_a_copy_stops_matching_its_source(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        landed = pi_config.deploy(str(clone), str(dest), [])
        (pathlib.Path(landed) / "AGENTS.md").write_text("edited at the destination")

        with pytest.raises(SystemExit, match="does not match source"):
            pi_config.doctor(str(clone), landed, [], [])

    def test_fails_when_a_link_becomes_a_copy(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        landed = pathlib.Path(pi_config.deploy(str(clone), str(dest), []))
        (landed / "settings.json").unlink()
        (landed / "settings.json").write_text("{}")

        with pytest.raises(SystemExit, match="not a symlink"):
            pi_config.doctor(str(clone), str(landed), [], [])

    def test_fails_when_a_link_points_somewhere_else(
        self, clone: pathlib.Path, dest: pathlib.Path, tmp_path: pathlib.Path
    ) -> None:
        landed = pathlib.Path(pi_config.deploy(str(clone), str(dest), []))
        decoy = tmp_path / "decoy.json"
        decoy.write_text("{}")
        (landed / "settings.json").unlink()
        (landed / "settings.json").symlink_to(decoy)

        with pytest.raises(SystemExit, match="want"):
            pi_config.doctor(str(clone), str(landed), [], [])

    def test_fails_when_auth_json_is_readable_by_others(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        landed = pathlib.Path(pi_config.deploy(str(clone), str(dest), []))
        auth = landed / "auth.json"
        auth.write_text('{"token":"secret"}')
        auth.chmod(0o644)

        with pytest.raises(SystemExit, match="auth.json mode"):
            pi_config.doctor(str(clone), str(landed), [], [])

    def test_fails_when_the_destination_carries_the_clone_rules(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        """Landing them would give the agent this repo's rules everywhere."""
        landed = pathlib.Path(pi_config.deploy(str(clone), str(dest), []))
        payload = clone / "home" / ".pi" / "agent" / "AGENTS.md"
        payload.write_text((clone / "AGENTS.md").read_text())
        (landed / "AGENTS.md").write_text((clone / "AGENTS.md").read_text())

        with pytest.raises(SystemExit, match="clone-rules file"):
            pi_config.doctor(str(clone), str(landed), [], [])
