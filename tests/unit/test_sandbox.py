"""The host literals of the pi-sandbox policy: what a scan finds, what a
rewrite replaces, and what it must leave alone.

pi-sandbox denies a project `.envrc.local` only by its literal path, so a
scan that misses one, or a rewrite that drops a hand-written entry, opens a
secret with no error anywhere.
"""

from __future__ import annotations

import json
import pathlib
import socket

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


def touch(path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n")


@pytest.fixture
def clone(tmp_path: pathlib.Path) -> pathlib.Path:
    """A source tree that holds only the policy."""
    root = tmp_path / "clone"
    policy = {
        "enabled": True,
        "filesystem": {
            "allowRead": ["."],
            "denyRead": [
                "/home",
                "~/Projects/gone/.envrc.local",
                "~/.ssh/keys",
                "/tmp-k/kitty-old",
                "/run/user/1000/bus",
            ],
            "denyWrite": [".pi"],
        },
    }
    path = root / pi_config.SANDBOX_REL
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(policy, indent=2) + "\n")
    return root


def deny_read(clone: pathlib.Path) -> list[str]:
    policy = json.loads((clone / pi_config.SANDBOX_REL).read_text())
    return policy["filesystem"]["denyRead"]


class TestScanEnvrcs:
    def test_finds_each_file_at_any_depth_spelled_with_tilde(
        self, tmp_home: pathlib.Path
    ) -> None:
        touch(tmp_home / "Projects" / "a" / ".envrc.local")
        touch(tmp_home / "Projects" / "x.ws" / "b@feat" / ".envrc.local")
        assert pi_config.scan_envrcs(str(tmp_home)) == [
            "~/Projects/a/.envrc.local",
            "~/Projects/x.ws/b@feat/.envrc.local",
        ]

    def test_skips_install_trees_and_git(self, tmp_home: pathlib.Path) -> None:
        touch(tmp_home / "Projects" / "a" / "node_modules" / "p" / ".envrc.local")
        touch(tmp_home / "Projects" / "a" / ".git" / ".envrc.local")
        assert pi_config.scan_envrcs(str(tmp_home)) == []

    def test_a_home_with_no_projects_folder_has_none(
        self, tmp_home: pathlib.Path
    ) -> None:
        assert pi_config.scan_envrcs(str(tmp_home)) == []


class TestScanKittySockets:
    def test_lists_sockets_only(self, tmp_path: pathlib.Path) -> None:
        kitty = tmp_path / "k"
        kitty.mkdir()
        (kitty / "kitty-file").write_text("")
        (kitty / "other").write_text("")
        server = socket.socket(socket.AF_UNIX)
        server.bind(str(kitty / "kitty-1"))
        try:
            assert pi_config.scan_kitty_sockets(str(kitty)) == [str(kitty / "kitty-1")]
        finally:
            server.close()

    def test_a_missing_folder_has_none(self, tmp_path: pathlib.Path) -> None:
        assert pi_config.scan_kitty_sockets(str(tmp_path / "absent")) == []


class TestRefresh:
    def test_replaces_the_host_literals_and_keeps_the_rest(
        self, clone: pathlib.Path, tmp_home: pathlib.Path
    ) -> None:
        touch(tmp_home / "Projects" / "new" / ".envrc.local")
        changed = pi_config.refresh_host_literals(
            str(clone), str(tmp_home), kitty_dir="/tmp-k"
        )
        assert changed
        assert deny_read(clone) == [
            "/home",
            "~/.ssh/keys",
            "/run/user/1000/bus",
            "~/Projects/new/.envrc.local",
        ]

    def test_a_second_run_writes_nothing(
        self, clone: pathlib.Path, tmp_home: pathlib.Path
    ) -> None:
        touch(tmp_home / "Projects" / "new" / ".envrc.local")
        pi_config.refresh_host_literals(str(clone), str(tmp_home), kitty_dir="/tmp-k")
        before = (clone / pi_config.SANDBOX_REL).stat().st_mtime_ns
        assert not pi_config.refresh_host_literals(
            str(clone), str(tmp_home), kitty_dir="/tmp-k"
        )
        assert (clone / pi_config.SANDBOX_REL).stat().st_mtime_ns == before

    def test_a_clone_without_the_policy_is_left_alone(
        self, tmp_path: pathlib.Path, tmp_home: pathlib.Path
    ) -> None:
        assert not pi_config.refresh_host_literals(str(tmp_path), str(tmp_home))

    def test_writes_the_bytes_pi_sandbox_writes(
        self, clone: pathlib.Path, tmp_home: pathlib.Path
    ) -> None:
        pi_config.refresh_host_literals(str(clone), str(tmp_home), kitty_dir="/tmp-k")
        text = (clone / pi_config.SANDBOX_REL).read_text()
        assert text == json.dumps(json.loads(text), indent=2) + "\n"


class TestMissingEnvrcs:
    def test_names_each_unlisted_file(
        self, clone: pathlib.Path, tmp_home: pathlib.Path
    ) -> None:
        touch(tmp_home / "Projects" / "new" / ".envrc.local")
        assert pi_config.missing_envrcs(str(clone), str(tmp_home)) == [
            "~/Projects/new/.envrc.local"
        ]

    def test_doctor_fails_until_deploy_refreshes(
        self, clone: pathlib.Path, tmp_home: pathlib.Path
    ) -> None:
        touch(tmp_home / "Projects" / "new" / ".envrc.local")
        with pytest.raises(SystemExit, match="does not deny"):
            pi_config.prove_envrcs_denied(str(clone))
        pi_config.refresh_host_literals(str(clone), str(tmp_home))
        pi_config.prove_envrcs_denied(str(clone))
