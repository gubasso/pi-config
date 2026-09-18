"""The veto in front of every deletion.

The manifest is trusted state, not proof. It sits at the destination, so
anything able to write there could name `auth.json` or a session transcript
for deletion. These tests cover the veto that sits behind it and the
classification that decides what a stale entry becomes.

If one file in this suite deserves to be read before it is edited, it is this
one. Every case here is a credential that does not get deleted.
"""

from __future__ import annotations

import pathlib

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


@pytest.fixture
def dest(tmp_home: pathlib.Path) -> pathlib.Path:
    path = tmp_home / ".pi" / "agent"
    path.mkdir(parents=True)
    return path


@pytest.fixture
def roots(dest: pathlib.Path) -> list[str]:
    return pi_config.landing_roots(str(dest))


class TestRuntimeOwnedNames:
    @pytest.mark.parametrize(
        "name",
        [
            "auth.json",
            "oauth.json",
            "models.json",
            "models-store.json",
            "trust.json",
            "mcp-cache.json",
            "web-search.json",
            "plan-mode.json",
            "broker.sock",
            "broker.pid",
            "broker.port.json",
        ],
    )
    def test_a_runtime_name_is_vetoed(
        self, name: str, dest: pathlib.Path, roots: list[str]
    ) -> None:
        assert pi_config.runtime_owned(str(dest / name), roots)

    @pytest.mark.parametrize("name", ["pi-debug.log", "anything.log"])
    def test_any_log_is_vetoed(
        self, name: str, dest: pathlib.Path, roots: list[str]
    ) -> None:
        assert pi_config.runtime_owned(str(dest / name), roots)

    def test_a_runtime_name_is_vetoed_at_any_depth(
        self, dest: pathlib.Path, roots: list[str]
    ) -> None:
        """intercom/ holds one file deploy owns and several the broker writes."""
        assert pi_config.runtime_owned(str(dest / "intercom" / "broker.sock"), roots)

    def test_keybindings_stays_prunable(
        self, dest: pathlib.Path, roots: list[str]
    ) -> None:
        """Deploy lands it when a source exists.

        Vetoing it would wedge every later deploy after the source is
        removed, because the stale row could never be cleared.
        """
        assert not pi_config.runtime_owned(str(dest / "keybindings.json"), roots)

    @pytest.mark.parametrize(
        "name", ["AGENTS.md", "settings.json", "99extensions.json"]
    )
    def test_what_deploy_lands_is_not_vetoed(
        self, name: str, dest: pathlib.Path, roots: list[str]
    ) -> None:
        assert not pi_config.runtime_owned(str(dest / name), roots)


class TestRuntimeOwnedDirs:
    @pytest.mark.parametrize(
        "directory",
        [
            "sessions",
            "npm",
            "git",
            "bin",
            "tmp",
            "tools",
            "web-search-cache",
            "missions",
            "pending-asks",
            "extension-state",
        ],
    )
    def test_anything_under_a_runtime_directory_is_vetoed(
        self, directory: str, dest: pathlib.Path, roots: list[str]
    ) -> None:
        target = dest / directory / "deep" / "file.json"
        assert pi_config.runtime_owned(str(target), roots)

    def test_the_veto_reads_the_path_relative_to_a_root(
        self, dest: pathlib.Path, roots: list[str]
    ) -> None:
        """A dest under /tmp must not veto every prune.

        Matching directory names against the absolute path would make `tmp`
        anywhere above the root disable pruning entirely, which is exactly
        the shape a temporary directory has.
        """
        assert not pi_config.runtime_owned(str(dest / "AGENTS.md"), roots)

    def test_an_in_root_symlink_cannot_launder_a_transcript(
        self, dest: pathlib.Path, roots: list[str]
    ) -> None:
        """`dest/legacy -> dest/sessions` stays physically inside the root.

        A lexical-only check would pass it and carry a stale row into a
        session transcript.
        """
        (dest / "sessions").mkdir()
        (dest / "legacy").symlink_to(dest / "sessions")

        assert pi_config.runtime_owned(str(dest / "legacy" / "a.jsonl"), roots)


class TestPruneMode:
    @pytest.mark.usefixtures("tmp_home")
    def test_defaults_to_apply(self) -> None:
        assert pi_config.prune_mode() == "apply"

    @pytest.mark.parametrize("mode", ["apply", "report", "adopt"])
    def test_accepts_the_three_modes(
        self, mode: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PI_CONFIG_PRUNE", mode)
        assert pi_config.prune_mode() == mode

    @pytest.mark.parametrize("mode", ["delete", "yes", "APPLY", ""])
    def test_refuses_anything_else(
        self, mode: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A typo must fail the run, never fall back to deleting."""
        monkeypatch.setenv("PI_CONFIG_PRUNE", mode)
        with pytest.raises(SystemExit):
            pi_config.prune_mode()


class TestClassifyStale:
    """What one path the repo no longer declares becomes.

    First match wins, and `prune` is the only verdict that deletes. Anything
    the engine refuses raises instead of returning, so a corrupted manifest
    fails the run rather than being skipped quietly and forgotten.
    """

    @pytest.fixture
    def clone(self, tmp_path: pathlib.Path) -> pathlib.Path:
        path = tmp_path / "clone"
        path.mkdir()
        return path

    def test_a_path_deploy_landed_before_is_pruned(
        self, clone: pathlib.Path, dest: pathlib.Path, roots: list[str]
    ) -> None:
        target = dest / "prompts" / "gone.md"
        target.parent.mkdir()
        target.write_text("x")

        verdict = pi_config.classify_stale(
            str(clone), roots, str(target), "copy", set()
        )
        assert verdict == "prune"

    def test_a_path_already_absent_is_gone_not_an_error(
        self, clone: pathlib.Path, dest: pathlib.Path, roots: list[str]
    ) -> None:
        verdict = pi_config.classify_stale(
            str(clone), roots, str(dest / "never-existed.md"), "copy", set()
        )
        assert verdict == "gone"

    def test_the_manifest_itself_is_kept(
        self, clone: pathlib.Path, dest: pathlib.Path, roots: list[str]
    ) -> None:
        target = dest / pi_config.MANIFEST_NAME
        target.write_text("{}")

        verdict = pi_config.classify_stale(
            str(clone), roots, str(target), "copy", set()
        )
        assert verdict == "keep"

    def test_a_protected_destination_is_kept(
        self, clone: pathlib.Path, dest: pathlib.Path, roots: list[str]
    ) -> None:
        """A live-only sidecar can hold tokens, and deploy never touches it."""
        target = dest / "some-live-only.json"
        target.write_text("{}")

        verdict = pi_config.classify_stale(
            str(clone), roots, str(target), "copy", {str(target)}
        )
        assert verdict == "keep"
        assert target.exists()

    def test_a_directory_recorded_as_a_file_is_refused(
        self, clone: pathlib.Path, dest: pathlib.Path, roots: list[str]
    ) -> None:
        """os.remove would fail on it, and a recursive delete is never used."""
        target = dest / "prompts"
        target.mkdir()

        verdict = pi_config.classify_stale(
            str(clone), roots, str(target), "copy", set()
        )
        assert verdict == "refused"
        assert target.is_dir()

    def test_a_runtime_owned_path_fails_the_run(
        self, clone: pathlib.Path, dest: pathlib.Path, roots: list[str]
    ) -> None:
        target = dest / "auth.json"
        target.write_text('{"token":"secret"}')

        with pytest.raises(SystemExit, match="runtime-owned"):
            pi_config.classify_stale(str(clone), roots, str(target), "copy", set())
        assert target.read_text() == '{"token":"secret"}'

    def test_a_path_outside_every_root_fails_the_run(
        self, clone: pathlib.Path, roots: list[str], tmp_path: pathlib.Path
    ) -> None:
        outside = tmp_path / "outside.txt"
        outside.write_text("keep")

        with pytest.raises(SystemExit, match="landing roots"):
            pi_config.classify_stale(str(clone), roots, str(outside), "copy", set())
        assert outside.exists()

    def test_a_symlink_into_the_clone_is_pruned_without_following_it(
        self, clone: pathlib.Path, dest: pathlib.Path, roots: list[str]
    ) -> None:
        """Deploy symlinks into the clone, and the link is what gets removed.

        entry_path keeps the leaf, so containment judges the link rather than
        its target. Resolving the target would put every deployed symlink
        outside the landing roots and make it unprunable forever.
        """
        source = clone / "settings.json"
        source.write_text("{}")
        link = dest / "settings.json"
        link.symlink_to(source)

        verdict = pi_config.classify_stale(
            str(clone), roots, str(link), "symlink", set()
        )
        assert verdict == "prune"
        assert source.exists()

    def test_a_clone_under_a_landing_root_is_still_refused(
        self, tmp_home: pathlib.Path, dest: pathlib.Path, roots: list[str]
    ) -> None:
        """SPEC forbids cloning under ~/.pi. This is the guard if someone does.

        A clone anywhere else is already refused for being outside the
        landing roots, so this check is only reachable from inside one.
        """
        clone = tmp_home / ".pi" / "clone"
        clone.mkdir()
        source = clone / "settings.json"
        source.write_text("{}")

        with pytest.raises(SystemExit, match="inside the clone"):
            pi_config.classify_stale(str(clone), roots, str(source), "copy", set())
        assert source.exists()

    def test_a_store_symlink_fails_the_run(
        self, clone: pathlib.Path, dest: pathlib.Path, roots: list[str]
    ) -> None:
        """A store symlink means Home Manager still owns the destination."""
        target = dest / "AGENTS.md"
        target.symlink_to("/nix/store/does-not-exist-agents-md")

        with pytest.raises(SystemExit, match="store symlink"):
            pi_config.classify_stale(str(clone), roots, str(target), "copy", set())
