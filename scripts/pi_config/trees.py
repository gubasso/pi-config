"""Install-tree convergence, always through `pi remove`.

Deleting a tree by hand leaves the dependency in Pi's own package.json and
the next install resurrects it."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from .pins import npm_name
from .prune import prune_mode


def installed_npm(dest: str) -> dict[str, str]:
    """Packages npm has installed, read from the project manifest Pi maintains.

    Not a node_modules listing: that tree is one flat npm project holding
    every transitive dependency, so a directory scan reports dozens of false
    orphans. A dependency key is already `@scope/name`.
    """
    path = os.path.join(dest, "npm", "package.json")
    if not os.path.isfile(path):
        return {}
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    deps = data.get("dependencies")
    return dict(deps) if isinstance(deps, dict) else {}


def installed_git(dest: str) -> dict[str, str]:
    """Git clones under dest/git, keyed by the pin source that installed them."""
    root = os.path.join(dest, "git")
    out: dict[str, str] = {}
    if not os.path.isdir(root):
        return out
    for current, dirs, _ in os.walk(root):
        if ".git" in dirs or os.path.isdir(os.path.join(current, ".git")):
            rel = os.path.relpath(current, root).replace(os.sep, "/")
            out[f"git:{rel}"] = current
            dirs[:] = []
    return out


def pi_remove(source: str) -> tuple[int, str]:
    result = subprocess.run(
        ["pi", "remove", source],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def converge_trees(dest: str, pins: list[dict[str, str]]) -> None:
    """Remove an install tree whose pin has left settings.json.

    Always through `pi remove`. dest/npm is one real npm project with a
    package.json and a lockfile, so deleting a directory by hand leaves the
    dependency entry behind and the next install resurrects the tree.
    """
    declared_npm = {npm_name(row["pin"][4:]) for row in pins if row["kind"] == "npm"}
    declared_git = {row["pin"] for row in pins if row["kind"] == "git"}

    orphans: list[tuple[str, str]] = []
    for name in sorted(installed_npm(dest)):
        if name not in declared_npm:
            orphans.append((f"npm:{name}", "npm"))
    for source, tree in sorted(installed_git(dest).items()):
        if source not in declared_git and os.path.realpath(tree) not in {
            os.path.realpath(row["tree"]) for row in pins if row["tree"]
        }:
            orphans.append((source, "git"))

    print(
        f"pi-config: converging install trees ({len(pins)} pinned, {len(orphans)} orphaned)"
    )
    if not orphans:
        return
    for source, kind in orphans:
        print(f"  prune   {kind:<8} {source}")

    if prune_mode() == "report":
        print("pi-config: report only; no tree removed")
        return
    if not shutil.which("pi"):
        print(
            "note: pi is not on PATH; run pi remove for each orphan above",
            file=sys.stderr,
        )
        return

    for source, _ in orphans:
        code, output = pi_remove(source)
        # removeAndPersist uninstalls the tree first, then finds the pin
        # already gone from settings and exits 1. That is this exact case.
        if code == 1 and "No matching package found" in output:
            print(f'note: pi exited 1 with "No matching package found" for {source}')
        elif code != 0:
            raise SystemExit(f"pi remove {source} failed ({code}):\n{output}")
        if source.startswith("npm:") and source[4:] in installed_npm(dest):
            raise SystemExit(f"pi remove {source} left the dependency in place")
        print(f"removed tree {source}")


def note_trees(pins: list[dict[str, str]]) -> None:
    missing = False
    for row in pins:
        if row["tree"] and os.path.isdir(row["tree"]):
            print(f"ok  package tree {row['pin']}")
            continue
        missing = True
        print(
            f"note: package {row['pin']} tree missing; run pi update --extensions",
            file=sys.stderr,
        )
    if not missing and pins:
        print("ok  package trees")
