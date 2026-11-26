"""The host literals of the pi-sandbox policy, kept in step with the host.

pi-sandbox binds concrete paths only on Linux, so the policy names each
project `.envrc.local` and each old kitty socket by its own path. Those
paths come and go with the host. Deploy rewrites them in the tracked
`sandbox.json` before it lands, and doctor fails when an `.envrc.local`
exists that the policy does not deny.

Every other entry of the file belongs to a person and stays as written.
"""

from __future__ import annotations

import json
import os
import stat
from typing import Any

from .fsx import read_bytes, write_bytes

SANDBOX_REL = os.path.join("home", ".pi", "agent", "sandbox.json")

PROJECTS = "Projects"
ENVRC = ".envrc.local"
KITTY_DIR = "/tmp"
KITTY_PREFIX = "kitty-"

# Folders a scan never enters: install trees, build output, and git.
SKIP_DIRS = frozenset(
    {".git", ".direnv", "node_modules", ".venv", "target", "result", "__pycache__"}
)


def sandbox_source(src: str) -> str:
    return os.path.join(src, SANDBOX_REL)


def tilde(path: str, home: str) -> str:
    """Spell a path under the home folder the way the policy spells it."""
    rel = os.path.relpath(path, home)
    return "~/" + rel.replace(os.sep, "/")


def scan_envrcs(home: str) -> list[str]:
    """Every `.envrc.local` under `~/Projects`, spelled with `~`, sorted."""
    root = os.path.join(home, PROJECTS)
    found: list[str] = []
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        if ENVRC in files:
            found.append(tilde(os.path.join(current, ENVRC), home))
    return sorted(found)


def scan_kitty_sockets(kitty_dir: str = KITTY_DIR) -> list[str]:
    """Every kitty socket at the top of `kitty_dir`, as an absolute path."""
    if not os.path.isdir(kitty_dir):
        return []
    sockets = []
    for name in os.listdir(kitty_dir):
        if not name.startswith(KITTY_PREFIX):
            continue
        path = os.path.join(kitty_dir, name)
        try:
            mode = os.lstat(path).st_mode
        except OSError:
            continue
        if stat.S_ISSOCK(mode):
            sockets.append(path)
    return sorted(sockets)


def host_literal(entry: str, kitty_dir: str = KITTY_DIR) -> bool:
    """Whether deploy owns this `denyRead` entry."""
    if entry.startswith(f"~/{PROJECTS}/") and entry.endswith(f"/{ENVRC}"):
        return True
    return entry.startswith(os.path.join(kitty_dir, KITTY_PREFIX))


def with_host_literals(
    policy: dict[str, Any],
    envrcs: list[str],
    sockets: list[str],
    kitty_dir: str = KITTY_DIR,
) -> dict[str, Any]:
    """The policy with its host literals replaced, every other entry kept."""
    filesystem: dict[str, list[str]] = dict(policy["filesystem"])
    kept = [e for e in filesystem["denyRead"] if not host_literal(e, kitty_dir)]
    filesystem["denyRead"] = kept + envrcs + sockets
    return {**policy, "filesystem": filesystem}


def render(policy: dict[str, Any]) -> bytes:
    # The bytes pi-sandbox itself writes on a grant, so neither writer
    # reformats the other.
    return (json.dumps(policy, indent=2) + "\n").encode()


def refresh_host_literals(src: str, home: str, kitty_dir: str = KITTY_DIR) -> bool:
    """Rewrite the host literals of the tracked policy. True when it changed."""
    path = sandbox_source(src)
    if not os.path.isfile(path):
        return False
    before = read_bytes(path)
    policy = json.loads(before)
    after = render(
        with_host_literals(
            policy, scan_envrcs(home), scan_kitty_sockets(kitty_dir), kitty_dir
        )
    )
    if after == before:
        print("ok  sandbox host literals current")
        return False
    write_bytes(path, after)
    print(f"refreshed sandbox host literals in {SANDBOX_REL}; commit the change")
    return True


def missing_envrcs(src: str, home: str) -> list[str]:
    """Each `.envrc.local` on the host that the tracked policy does not deny."""
    path = sandbox_source(src)
    if not os.path.isfile(path):
        return []
    denied = set(json.loads(read_bytes(path))["filesystem"]["denyRead"])
    return [e for e in scan_envrcs(home) if e not in denied]
