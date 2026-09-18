"""What the operator sees: source, destination, pins, and sidecar state."""

from __future__ import annotations

import os
import shutil

from .fsx import same_inode
from .paths import plugin_docs_dir, sidecar_dest_path, sidecar_source_path


def describe(path: str, label: str) -> None:
    if os.path.islink(path):
        target = os.path.realpath(path)
        kind = "store-symlink" if "/nix/store/" in target else f"symlink {target}"
    elif os.path.exists(path):
        kind = "file"
    else:
        kind = "no"
    print(f"{label} {kind}")


def print_header(src: str, dest: str) -> None:
    """Where this run would read from and write to, before any detail."""
    print(f"source {src}")
    print(f"dest {dest}")
    override = os.environ.get("PI_CODING_AGENT_DIR")
    print(
        f"PI_CODING_AGENT_DIR {override}" if override else "PI_CODING_AGENT_DIR (unset)"
    )

    describe(os.path.join(dest, "AGENTS.md"), "dest AGENTS.md")
    describe(os.path.join(dest, "settings.json"), "dest settings.json")
    describe(os.path.join(dest, "auth.json"), "dest auth.json")

    found = shutil.which("pi")
    print(f"pi {found}" if found else "pi (missing)")


def print_status(
    src: str, dest: str, pins: list[dict[str, str]], sidecars: list[dict[str, object]]
) -> None:
    print_header(src, dest)
    if not pins:
        print("packages none")
        return
    for row in pins:
        docs = plugin_docs_dir(src, row["name"])
        docs_state = (
            "yes"
            if all(
                os.path.isfile(os.path.join(docs, name))
                for name in ("README.md", "SPEC.md", "sidecars.json")
            )
            else "no"
        )
        tree_state = "yes" if row["tree"] and os.path.isdir(row["tree"]) else "no"
        pin_state = f"frozen {row['frozen']}" if row["frozen"] else "unversioned"
        print(f"package {row['pin']} docs {docs_state} tree {tree_state} {pin_state}")
    for row in sidecars:
        rel = str(row["path"])
        dest_path = sidecar_dest_path(dest, row)
        if dest_path and os.path.islink(dest_path):
            state = "symlink"
        elif dest_path and os.path.isfile(dest_path):
            source_path = sidecar_source_path(src, rel)
            state = "hardlink" if same_inode(source_path, dest_path) else "file"
        else:
            state = "no"
        print(f"sidecar {rel} class {row['class']} dest {state}")
