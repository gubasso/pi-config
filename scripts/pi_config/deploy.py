"""Landing the payload, then converging what the repository stopped declaring.

This was three hundred lines of bash inside the justfile, which meant the
landing contract had two implementations in two languages joined by a
temp file. `store_owned` alone existed three times. It exists once now.

Order is the contract, and every step of it is load-bearing:

1.  Prove the landing roots before anything is written. A root that is a
    symlink redirects every copy and every deletion below it, and a guard
    that only ran at prune time would fire after the damage.
2.  Refuse a destination Home Manager still owns, because two writers on
    one file is the thing this whole repository exists to avoid.
3.  Land the static payload, the runtime-writable links, and the sidecars,
    recording each one as it lands.
4.  Converge: remove what the previous manifest recorded and this run did
    not land again.
5.  Prove the result with doctor, which repeats the source proof aloud.
6.  Converge install trees last, because `pi remove` runs npm and can need
    the network. A failure there leaves the config correct and only an
    install tree orphaned.
"""

from __future__ import annotations

import os

from .doctor import preflight
from .fsx import copy_regular, store_owned
from .landing import land_sidecars
from .manifest import record, reset_landed
from .paths import agent_payload_dir, landing_roots
from .prune import converge

# Copied wholesale when the directory exists. Stock Pi names, so landing is a
# copy of the path rather than a mapping anybody has to remember.
PAYLOAD_DIRS = ("prompts", "extensions", "themes", "skills", "agents")

# Copied when present. AGENTS.md is required; the other is not.
PAYLOAD_FILES = ("AGENTS.md", "APPEND_SYSTEM.md")

# Symlinked, because the runtime writes them and this repository tracks them.
# Pi's writeFileSync follows the link, so the write reaches git.
LINKED_FILES = ("settings.json", "keybindings.json")


def refuse_store_symlink(path: str, hint: str = "") -> None:
    if not store_owned(path):
        return
    message = f"Home Manager still owns {path} (store symlink)."
    if hint:
        message += f"\n{hint}"
    raise SystemExit(message)


def copy_file(source: str, dest_path: str) -> None:
    copy_regular(source, dest_path)
    record("copy", dest_path)
    print(f"copied {dest_path}")


def copy_dir_files(source_dir: str, dest_dir: str) -> None:
    """Copy the regular files of one directory, one level deep.

    One level, because Pi discovers a prompt, an extension, or a theme at the
    top of its directory. A subdirectory here would be landed nowhere and
    noticed by nobody, so tests/meta asserts none exists.
    """
    if os.path.islink(dest_dir):
        os.remove(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    record("dir", dest_dir)

    for name in sorted(os.listdir(source_dir)):
        source = os.path.join(source_dir, name)
        if not os.path.isfile(source):
            continue
        copy_file(source, os.path.join(dest_dir, name))


def link_tracked(source: str, dest_path: str) -> None:
    refuse_store_symlink(dest_path)
    if os.path.isdir(dest_path) and not os.path.islink(dest_path):
        raise SystemExit(f"refusing to replace directory {dest_path} with a symlink")
    if os.path.lexists(dest_path):
        os.remove(dest_path)
    os.symlink(os.path.abspath(source), dest_path)
    record("symlink", dest_path)
    print(f"linked {dest_path} -> {source}")


def prove_roots(dest: str) -> None:
    for root in landing_roots(dest):
        print(f"ok  landing root {root}")


def land_payload(src: str, dest: str) -> None:
    """Everything under home/.pi/agent/, copied or linked by its own path."""
    agent_src = agent_payload_dir(src)

    for name in PAYLOAD_FILES:
        source = os.path.join(agent_src, name)
        if os.path.isfile(source):
            copy_file(source, os.path.join(dest, name))

    for name in PAYLOAD_DIRS:
        source = os.path.join(agent_src, name)
        if os.path.isdir(source):
            copy_dir_files(source, os.path.join(dest, name))

    for name in LINKED_FILES:
        source = os.path.join(agent_src, name)
        if os.path.isfile(source):
            link_tracked(source, os.path.join(dest, name))


def deploy(
    src: str,
    dest: str,
    pins: list[dict[str, str]],
    sidecars: list[dict[str, object]],
) -> str:
    """Land everything the repository declares. Returns the resolved dest.

    Converging and proving are the caller's next two steps, because doctor
    has to run between the file convergence and the install-tree one.
    """
    reset_landed()

    # Before anything lands, and before anything is deleted.
    preflight(src, dest, pins, sidecars)
    prove_roots(dest)

    os.makedirs(dest, exist_ok=True)
    dest = os.path.realpath(dest)

    refuse_store_symlink(
        os.path.join(dest, "AGENTS.md"),
        "Thin the pi-coding-agent module, activate, then rerun just deploy.",
    )
    refuse_store_symlink(os.path.join(dest, "prompts"))
    refuse_store_symlink(os.path.join(dest, "settings.json"))

    land_payload(src, dest)
    land_sidecars(src, dest, sidecars)
    converge(src, dest, sidecars)
    return dest
