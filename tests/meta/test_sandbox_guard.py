"""The pi-sandbox policy keeps the properties its limits depend on.

`home/.pi/agent/sandbox.json` is the interim guard of every pi session.
pi-sandbox 0.8.2 enforces it in two different ways: bubblewrap for bash, and
a path check that ignores `denyRead` for the built-in read tool. Each test
below holds one property that a plausible edit of the file would break
without any error at runtime.
"""

from __future__ import annotations

import json
import pathlib

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]

PIN = "npm:pi-sandbox@0.8.2"
LIVE_LINK = "~/.pi/agent/sandbox.json"
SOURCE = "~/Projects/_gubasso/pi-config.ws/pi-config/home/.pi/agent/sandbox.json"

# The secret paths and escape sockets the guard was ordered to deny.
REQUIRED_DENY_READ = {
    "/home",
    "/run/user/1000/secrets.d",
    "~/.config/sops",
    "~/.ssh/keys",
    "~/.aws",
    "~/.gnupg/private-keys-v1.d",
    "~/.config/rclone",
    "~/.config/gh/hosts.yml",
    "~/.config/glab-cli",
    "~/.docker/config.json",
    "~/.claude/.credentials.json",
    "~/.codex/auth.json",
    "~/.pi/agent/auth.json",
    "/run/docker.sock",
    "/run/user/1000/bus",
    "/run/user/1000/systemd",
    "/run/user/1000/podman",
    "/run/user/1000/kitty",
    "/run/user/1000/gnupg",
    "/run/user/1000/ssh-agent.socket",
    "/tmp/.X11-unix",
    "/run/user/1000/at-spi",
    "/run/user/1000/app",
    "/run/user/1000/gvfsd",
    "/run/user/1000/agent-browser",
}

# A trusted project's `.pi` folder can turn the sandbox off or add an
# extension that runs outside it. airlock keeps its confirmations there.
REQUIRED_DENY_WRITE = {".pi", "~/.local/state/airlock"}


@pytest.fixture
def filesystem(repo_root: pathlib.Path) -> dict[str, list[str]]:
    config = json.loads((repo_root / "home/.pi/agent/sandbox.json").read_text())
    assert config["enabled"] is True
    return config["filesystem"]


def covers(parent: str, path: str) -> bool:
    return path == parent or path.startswith(parent.rstrip("/") + "/")


def test_the_pin_is_the_audited_release(repo_root: pathlib.Path) -> None:
    settings = json.loads((repo_root / "home/.pi/agent/settings.json").read_text())
    assert PIN in settings["packages"]
    spec = (repo_root / "docs/plugins/pi-sandbox/SPEC.md").read_text()
    assert "tag v0.8.2" in spec


def test_every_ordered_deny_is_listed(filesystem: dict[str, list[str]]) -> None:
    assert REQUIRED_DENY_READ <= set(filesystem["denyRead"])


def test_each_envrc_local_is_denied_by_its_own_path(
    filesystem: dict[str, list[str]],
) -> None:
    # bubblewrap binds concrete paths only, so a pattern would deny nothing.
    # The list is empty once no project keeps an `.envrc.local`.
    envrcs = [p for p in filesystem["denyRead"] if p.endswith("/.envrc.local")]
    assert all(p.startswith("~/Projects/") for p in envrcs)


def test_no_read_allowance_reopens_the_project_env_folder(
    filesystem: dict[str, list[str]],
) -> None:
    # The developer values of each project live in this folder. The deny of
    # `/home` covers it only while no allow entry reaches it.
    assert "/home" in filesystem["denyRead"]
    folder = "~/.config/project-env"
    allows = filesystem["allowRead"] + filesystem["allowWrite"]
    assert not [a for a in allows if covers(a, folder) or covers(folder, a)]


@pytest.mark.parametrize("key", ["allowRead", "denyRead", "allowWrite"])
def test_bash_lists_hold_literal_paths_only(
    filesystem: dict[str, list[str]], key: str
) -> None:
    assert not [p for p in filesystem[key] if any(c in p for c in "*?[")]


def test_no_read_allowance_covers_a_denied_path(
    filesystem: dict[str, list[str]],
) -> None:
    # The built-in read tool checks allowRead and never denyRead, so an allow
    # entry above a deny entry reopens that secret to it. The session folder
    # `.` is the one known exception, and the README states it. `/tmp` holds
    # only sockets on the deny list, and a file read of a socket fails.
    allows = [
        p
        for p in filesystem["allowRead"] + filesystem["allowWrite"]
        if p not in {".", "/tmp"}
    ]
    denies = [p for p in filesystem["denyRead"] if p != "/home"]
    assert not [(a, d) for a in allows for d in denies if covers(a, d)]


def test_no_whole_config_or_state_folder_is_readable(
    filesystem: dict[str, list[str]],
) -> None:
    too_wide = {
        "~",
        "/",
        "/home",
        "~/.config",
        "~/.local",
        "~/.local/share",
        "~/.pi",
        "~/.pi/agent",
    }
    assert not too_wide & set(filesystem["allowRead"])


def test_the_guard_denies_writes_to_its_own_policy(
    filesystem: dict[str, list[str]],
) -> None:
    deny = filesystem["denyWrite"]
    # sandbox-runtime 0.0.80 keeps the first spelling of one file and drops
    # the bind when that spelling is the live link under the /home tmpfs.
    assert deny.index(SOURCE) < deny.index(LIVE_LINK)


def test_no_session_can_rewrite_its_own_rules(filesystem: dict[str, list[str]]) -> None:
    assert REQUIRED_DENY_WRITE <= set(filesystem["denyWrite"])
