"""What the operator sees: source, destination, pins, and sidecar state."""

from __future__ import annotations

import os

from .fsx import same_inode
from .paths import plugin_docs_dir, sidecar_dest_path, sidecar_source_path


def print_status(
    src: str, dest: str, pins: list[dict[str, str]], sidecars: list[dict[str, object]]
) -> None:
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
