"""Converging a destination: what leaves, what is only reported, what stays.

`converge` is the function that deletes. It reads what this run landed, reads
what the last run landed, and removes the difference. Everything it refuses
along the way has a test in tests/unit/test_prune.py; this file covers the
whole pass, including the order deletions happen in.

The scan and the adopt boundary live in `prune` and are driven from here,
because both build real trees on disk. They are two halves of one rule: the
report reaches every depth under the destination, and adopt does not.

`converge_trees` is the other half: an install tree whose pin left
settings.json, removed through `pi remove` rather than by hand.
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


@pytest.fixture
def clone(tmp_path: pathlib.Path, tmp_home: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "clone"
    (root / "home" / ".pi" / "agent").mkdir(parents=True)
    return root


@pytest.fixture
def dest(tmp_home: pathlib.Path) -> pathlib.Path:
    path = tmp_home / ".pi" / "agent"
    path.mkdir(parents=True)
    return path


@pytest.fixture
def landed(tmp_home: pathlib.Path):
    """Record what this run landed, the way deploy does."""
    pi_config.reset_landed()

    def record(how: str, path: pathlib.Path) -> None:
        pi_config.record(how, str(path))

    return record


def previous_manifest(dest: pathlib.Path, rows: list[tuple[str, str]]) -> None:
    (dest / pi_config.MANIFEST_NAME).write_text(
        json.dumps(
            {
                "version": pi_config.MANIFEST_VERSION,
                "deployedAt": "2026-01-01T00:00:00Z",
                "source": "/src",
                "paths": [{"path": path, "how": how} for path, how in rows],
            }
        )
    )


class TestConverge:
    def test_removes_what_this_run_did_not_land_again(
        self, clone: pathlib.Path, dest: pathlib.Path, landed
    ) -> None:
        keep = dest / "AGENTS.md"
        keep.write_text("keep")
        gone = dest / "prompts" / "old.md"
        gone.parent.mkdir()
        gone.write_text("gone")

        landed("dir", dest / "prompts")
        landed("copy", keep)
        previous_manifest(
            dest, [(str(keep), "copy"), (str(gone), "copy"), (str(gone.parent), "dir")]
        )

        pi_config.converge(str(clone), str(dest), [])

        assert keep.exists()
        assert not gone.exists()

    def test_removes_an_emptied_directory_it_created(
        self, clone: pathlib.Path, dest: pathlib.Path, landed
    ) -> None:
        stale_dir = dest / "themes"
        stale_dir.mkdir()
        stale_file = stale_dir / "old.json"
        stale_file.write_text("{}")

        landed("copy", dest / "AGENTS.md")
        (dest / "AGENTS.md").write_text("x")
        previous_manifest(
            dest,
            [
                (str(dest / "AGENTS.md"), "copy"),
                (str(stale_file), "copy"),
                (str(stale_dir), "dir"),
            ],
        )

        pi_config.converge(str(clone), str(dest), [])

        assert not stale_dir.exists()

    def test_keeps_a_directory_something_else_still_uses(
        self, clone: pathlib.Path, dest: pathlib.Path, landed
    ) -> None:
        """os.rmdir, never a recursive delete, so an occupant saves the tree."""
        shared = dest / "prompts"
        shared.mkdir()
        stale = shared / "old.md"
        stale.write_text("gone")
        runtime = shared / "written-by-a-package.md"
        runtime.write_text("keep")

        landed("copy", dest / "AGENTS.md")
        (dest / "AGENTS.md").write_text("x")
        previous_manifest(
            dest,
            [
                (str(dest / "AGENTS.md"), "copy"),
                (str(stale), "copy"),
                (str(shared), "dir"),
            ],
        )

        pi_config.converge(str(clone), str(dest), [])

        assert not stale.exists()
        assert shared.is_dir()
        assert runtime.read_text() == "keep"

    def test_report_mode_deletes_nothing(
        self,
        clone: pathlib.Path,
        dest: pathlib.Path,
        landed,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PI_CONFIG_PRUNE", "report")
        stale = dest / "old.md"
        stale.write_text("gone")
        landed("copy", dest / "AGENTS.md")
        (dest / "AGENTS.md").write_text("x")
        previous_manifest(
            dest, [(str(dest / "AGENTS.md"), "copy"), (str(stale), "copy")]
        )

        pi_config.converge(str(clone), str(dest), [])

        assert stale.exists()

    def test_a_first_run_with_no_previous_manifest_deletes_nothing(
        self, clone: pathlib.Path, dest: pathlib.Path, landed
    ) -> None:
        """An absent manifest means an unknown extent, not an empty one."""
        stranger = dest / "was-already-here.md"
        stranger.write_text("keep")
        landed("copy", dest / "AGENTS.md")
        (dest / "AGENTS.md").write_text("x")

        pi_config.converge(str(clone), str(dest), [])

        assert stranger.exists()

    def test_writes_the_new_manifest_from_what_this_run_landed(
        self, clone: pathlib.Path, dest: pathlib.Path, landed
    ) -> None:
        (dest / "AGENTS.md").write_text("x")
        landed("copy", dest / "AGENTS.md")

        pi_config.converge(str(clone), str(dest), [])

        rows = pi_config.read_manifest(str(dest))
        assert [row["path"] for row in rows] == [str(dest / "AGENTS.md")]


class TestUnmanagedPaths:
    def test_names_a_file_deploy_never_landed(self, dest: pathlib.Path) -> None:
        stranger = dest / "predates-the-manifest.md"
        stranger.write_text("x")

        assert pi_config.unmanaged_paths(str(dest), [], set()) == [str(stranger)]

    def test_ignores_what_this_run_landed(self, dest: pathlib.Path) -> None:
        mine = dest / "AGENTS.md"
        mine.write_text("x")

        got = pi_config.unmanaged_paths(str(dest), [(str(mine), "copy")], set())
        assert got == []

    def test_ignores_a_protected_live_only_destination(
        self, dest: pathlib.Path
    ) -> None:
        secret = dest / "some-live-only.json"
        secret.write_text("{}")

        got = pi_config.unmanaged_paths(str(dest), [], {str(secret)})
        assert got == []

    @pytest.mark.parametrize("name", ["auth.json", "trust.json", "pi-debug.log"])
    def test_ignores_a_runtime_owned_name(self, dest: pathlib.Path, name: str) -> None:
        (dest / name).write_text("x")
        assert pi_config.unmanaged_paths(str(dest), [], set()) == []

    def test_ignores_a_runtime_owned_directory(self, dest: pathlib.Path) -> None:
        (dest / "sessions").mkdir()
        (dest / "sessions" / "a.jsonl").write_text("{}")
        assert pi_config.unmanaged_paths(str(dest), [], set()) == []

    def test_ignores_the_manifest_itself(self, dest: pathlib.Path) -> None:
        (dest / pi_config.MANIFEST_NAME).write_text("{}")
        assert pi_config.unmanaged_paths(str(dest), [], set()) == []

    def test_reaches_into_a_directory_deploy_created(self, dest: pathlib.Path) -> None:
        managed = dest / "prompts"
        managed.mkdir()
        stranger = managed / "left-over.md"
        stranger.write_text("x")

        got = pi_config.unmanaged_paths(str(dest), [(str(managed), "dir")], set())
        assert got == [str(stranger)]

    def test_reaches_into_a_directory_deploy_never_created(
        self, dest: pathlib.Path
    ) -> None:
        """The case the Home Manager migration leaves behind.

        Nothing in the manifest names this directory, so prune cannot see it
        and the old scan skipped it whole. The file inside it is the leftover.
        """
        stray = dest / "themes"
        stray.mkdir()
        stranger = stray / "left-over.json"
        stranger.write_text("{}")

        assert pi_config.unmanaged_paths(str(dest), [], set()) == [str(stranger)]

    def test_descends_past_one_level(self, dest: pathlib.Path) -> None:
        deep = dest / "themes" / "dark" / "parts"
        deep.mkdir(parents=True)
        stranger = deep / "left-over.json"
        stranger.write_text("{}")

        assert pi_config.unmanaged_paths(str(dest), [], set()) == [str(stranger)]

    def test_names_an_empty_stray_directory(self, dest: pathlib.Path) -> None:
        """It holds no file to name it, and it is still a leftover."""
        stray = dest / "themes"
        stray.mkdir()

        assert pi_config.unmanaged_paths(str(dest), [], set()) == [str(stray)]

    def test_does_not_name_a_stray_directory_its_files_already_name(
        self, dest: pathlib.Path
    ) -> None:
        stray = dest / "themes"
        (stray / "dark").mkdir(parents=True)
        stranger = stray / "dark" / "left-over.json"
        stranger.write_text("{}")

        assert pi_config.unmanaged_paths(str(dest), [], set()) == [str(stranger)]

    def test_ignores_a_runtime_owned_directory_at_any_depth(
        self, dest: pathlib.Path
    ) -> None:
        deep = dest / "sessions" / "2026" / "01"
        deep.mkdir(parents=True)
        (deep / "a.jsonl").write_text("{}")

        assert pi_config.unmanaged_paths(str(dest), [], set()) == []

    def test_ignores_a_runtime_owned_directory_inside_a_managed_one(
        self, dest: pathlib.Path
    ) -> None:
        managed = dest / "extensions"
        state = managed / "extension-state"
        state.mkdir(parents=True)
        (state / "subagent.json").write_text("{}")

        got = pi_config.unmanaged_paths(str(dest), [(str(managed), "dir")], set())
        assert got == []

    def test_ignores_a_runtime_owned_name_inside_a_managed_directory(
        self, dest: pathlib.Path
    ) -> None:
        """The broker writes these beside the one file deploy owns."""
        managed = dest / "intercom"
        managed.mkdir()
        (managed / "broker.port.json").write_text("{}")
        (managed / "broker.pid").write_text("1")

        got = pi_config.unmanaged_paths(str(dest), [(str(managed), "dir")], set())
        assert got == []

    def test_names_a_symlinked_directory_without_descending_into_it(
        self, dest: pathlib.Path, tmp_path: pathlib.Path
    ) -> None:
        """One entry, not a tree. Whatever it points at is not this dest."""
        outside = tmp_path / "elsewhere"
        outside.mkdir()
        (outside / "not-ours.json").write_text("{}")
        link = dest / "themes"
        link.symlink_to(outside)

        assert pi_config.unmanaged_paths(str(dest), [], set()) == [str(link)]


class TestAdoptBoundary:
    """What adopt may delete, which is narrower than what the scan reports.

    RUNTIME_OWNED_DIRS is a fixed list of names. A directory outside it is not
    proven safe to empty, so adopt stays at the destination root and inside
    the directories deploy landed.
    """

    def test_covers_the_destination_root(self, dest: pathlib.Path) -> None:
        boundary = pi_config.adopt_boundary(str(dest), [])
        assert pi_config.within_adopt_boundary(str(dest / "loose.md"), boundary)

    def test_covers_a_directory_this_run_landed(self, dest: pathlib.Path) -> None:
        managed = dest / "prompts"
        managed.mkdir()
        boundary = pi_config.adopt_boundary(str(dest), [(str(managed), "dir")])
        assert pi_config.within_adopt_boundary(str(managed / "old.md"), boundary)

    def test_stops_at_a_directory_deploy_never_landed(self, dest: pathlib.Path) -> None:
        stray = dest / "themes"
        stray.mkdir()
        boundary = pi_config.adopt_boundary(str(dest), [])
        assert not pi_config.within_adopt_boundary(str(stray / "old.json"), boundary)


class TestAdoptStopsAtTheBoundary:
    """Adopt deletes where the scan reports, and no further.

    Characterization of the deletion set: these rows say that widening the
    report did not widen what `just deploy-adopt` removes.
    """

    def test_removes_a_loose_file_at_the_destination_root(
        self,
        clone: pathlib.Path,
        dest: pathlib.Path,
        landed,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PI_CONFIG_PRUNE", "adopt")
        stranger = dest / "predates-the-manifest.md"
        stranger.write_text("x")
        (dest / "AGENTS.md").write_text("x")
        landed("copy", dest / "AGENTS.md")

        pi_config.converge(str(clone), str(dest), [])

        assert not stranger.exists()

    def test_removes_a_file_inside_a_directory_deploy_landed(
        self,
        clone: pathlib.Path,
        dest: pathlib.Path,
        landed,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PI_CONFIG_PRUNE", "adopt")
        managed = dest / "prompts"
        managed.mkdir()
        stranger = managed / "left-over.md"
        stranger.write_text("x")
        landed("dir", managed)
        (dest / "AGENTS.md").write_text("x")
        landed("copy", dest / "AGENTS.md")

        pi_config.converge(str(clone), str(dest), [])

        assert not stranger.exists()

    def test_keeps_a_file_inside_a_directory_deploy_never_landed(
        self,
        clone: pathlib.Path,
        dest: pathlib.Path,
        landed,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PI_CONFIG_PRUNE", "adopt")
        stray = dest / "themes"
        stray.mkdir()
        stranger = stray / "left-over.json"
        stranger.write_text("{}")
        (dest / "AGENTS.md").write_text("x")
        landed("copy", dest / "AGENTS.md")

        pi_config.converge(str(clone), str(dest), [])

        assert stranger.read_text() == "{}"
        out = capsys.readouterr().out
        assert "remove it by hand" in out
        assert str(stranger) in out

    def test_no_line_promises_a_removal_that_does_not_happen(
        self,
        clone: pathlib.Path,
        dest: pathlib.Path,
        landed,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The sentence and the behavior come from one boundary function."""
        monkeypatch.setenv("PI_CONFIG_PRUNE", "report")
        stray = dest / "themes"
        stray.mkdir()
        (stray / "left-over.json").write_text("{}")
        loose = dest / "loose.md"
        loose.write_text("x")
        (dest / "AGENTS.md").write_text("x")
        landed("copy", dest / "AGENTS.md")

        pi_config.converge(str(clone), str(dest), [])

        lines = [
            line for line in capsys.readouterr().out.splitlines() if "unmanaged" in line
        ]
        promised = [line for line in lines if "deploy-adopt removes it" in line]
        assert promised == [
            f"  unmanaged        {loose} (just deploy-adopt removes it)"
        ]


class TestUnmanagedReport:
    def test_caps_the_lines_and_says_how_many_it_held_back(
        self,
        clone: pathlib.Path,
        dest: pathlib.Path,
        landed,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A stray tree can be large. The scan stays complete, the output does not."""
        extra = 3
        for index in range(pi_config.UNMANAGED_REPORT_LIMIT + extra):
            (dest / f"left-over-{index:04d}.md").write_text("x")
        (dest / "AGENTS.md").write_text("x")
        landed("copy", dest / "AGENTS.md")

        pi_config.converge(str(clone), str(dest), [])

        out = capsys.readouterr().out
        named = [line for line in out.splitlines() if "left-over-" in line]
        assert len(named) == pi_config.UNMANAGED_REPORT_LIMIT
        assert f"... and {extra} more, not shown" in out


class TestLiveOnlyDests:
    def test_collects_only_the_live_only_rows(self, dest: pathlib.Path) -> None:
        rows: list[dict[str, object]] = [
            {"path": ".pi/agent/secret.json", "class": "live-only"},
            {"path": ".pi/agent/thing.json", "class": "copy"},
        ]
        got = pi_config.live_only_dests(str(dest), rows)
        assert got == {str(dest / "secret.json")}


class TestConvergeTrees:
    @pytest.fixture(autouse=True)
    def stub_pi(
        self,
        repo_root: pathlib.Path,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> pathlib.Path:
        # Created empty, so a test asserting that nothing was called reads a
        # file rather than a FileNotFoundError.
        log = tmp_path / "pi-calls.log"
        log.write_text("")
        monkeypatch.setenv("PI_STUB_LOG", str(log))
        stubs = repo_root / "tests" / "helpers" / "stubs"
        monkeypatch.setenv("PATH", f"{stubs}{os.pathsep}{os.environ['PATH']}")
        return log

    def npm_project(self, dest: pathlib.Path, deps: dict[str, str]) -> None:
        npm = dest / "npm"
        npm.mkdir(exist_ok=True)
        (npm / "package.json").write_text(json.dumps({"dependencies": deps}))

    def test_removes_an_npm_tree_whose_pin_is_gone(
        self, dest: pathlib.Path, stub_pi: pathlib.Path
    ) -> None:
        self.npm_project(dest, {"pi-orphan": "1.0.0"})

        pi_config.converge_trees(str(dest), [])

        assert "remove npm:pi-orphan" in stub_pi.read_text()

    def test_keeps_a_tree_the_pins_still_declare(
        self, dest: pathlib.Path, stub_pi: pathlib.Path
    ) -> None:
        self.npm_project(dest, {"pi-kept": "1.0.0"})
        pins = [
            {
                "pin": "npm:pi-kept",
                "name": "pi-kept",
                "kind": "npm",
                "tree": "",
                "frozen": "",
            }
        ]

        pi_config.converge_trees(str(dest), pins)

        assert stub_pi.read_text() == ""

    def test_treats_an_already_absent_package_as_success(
        self, dest: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`pi remove` exits 1 with that sentence once the tree is gone."""
        monkeypatch.setenv("PI_STUB_PI_REMOVE_MISSING", "1")
        self.npm_project(dest, {"pi-orphan": "1.0.0"})

        pi_config.converge_trees(str(dest), [])

    def test_does_nothing_when_no_install_tree_exists(
        self, dest: pathlib.Path, stub_pi: pathlib.Path
    ) -> None:
        pi_config.converge_trees(str(dest), [])
        assert stub_pi.read_text() == ""

    def test_fails_when_pi_reports_success_but_leaves_the_dependency(
        self, dest: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Deleting the tree by hand leaves the entry and the next install
        resurrects it, so a half-done removal must not read as done."""
        monkeypatch.setenv("PI_STUB_PI_REMOVE_KEEPS", "1")
        self.npm_project(dest, {"pi-orphan": "1.0.0"})

        with pytest.raises(SystemExit, match="left the dependency in place"):
            pi_config.converge_trees(str(dest), [])
