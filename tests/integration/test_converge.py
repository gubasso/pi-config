"""Converging a destination: what leaves, what is only reported, what stays.

`converge` is the function that deletes. It reads what this run landed, reads
what the last run landed, and removes the difference. Everything it refuses
along the way has a test in tests/unit/test_prune.py; this file covers the
whole pass, including the order deletions happen in.

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
def landed(
    tmp_path: pathlib.Path, tmp_home: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    """Record what this run landed, the way the deploy recipe does."""
    run = tmp_path / "run-manifest"
    run.write_text("")
    monkeypatch.setenv("PI_CONFIG_RUN_MANIFEST", str(run))

    def record(how: str, path: pathlib.Path) -> None:
        with run.open("a") as handle:
            handle.write(f"{how}\t{path}\n")

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
