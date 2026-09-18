"""What may be removed from the destination, and what may not.

The manifest is trusted state, not proof. It sits at the destination, so
anything able to write there could name auth.json for deletion. The veto
here is what stands behind it.

Two questions live in this module and nowhere else: whether a path is
runtime-owned, and which paths at the destination no deploy ever landed.
`converge` is the pass that acts on the answers."""

from __future__ import annotations

import os

from .fsx import store_owned
from .manifest import MANIFEST_NAME
from .paths import entry_path, sidecar_dest_path, within_root

# Names Pi and its packages write into the live agent dir. Deploy never
# creates any of them, so none can enter the manifest and prune cannot reach
# them. This list is advisory only: it keeps the unmanaged scan quiet. A name
# missing here costs a spurious note, never a deletion.
RUNTIME_OWNED_NAMES = {
    "auth.json",
    "oauth.json",
    "keybindings.json",
    "models.json",
    "models-store.json",
    "trust.json",
    "mcp-cache.json",
    "web-search.json",
    "plan-mode.json",
    "pi-debug.log",
    # pi-intercom broker runtime, which sits beside the one file deploy owns
    # in intercom/. The scan reaches into managed directories, so these names
    # must be honoured at every level, not only at the dest root.
    "broker.sock",
    "broker.pid",
    "broker.port.json",
    "broker.spawn.lock",
    "broker-launch.vbs",
}


RUNTIME_OWNED_DIRS = {
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
}


# keybindings.json is in RUNTIME_OWNED_NAMES because Pi writes it when this
# repo does not track it. Deploy does land it when a source exists, so a stale
# row for it must stay prunable, or removing that source wedges every later
# deploy. The scan still stays quiet about an untracked one.
PRUNE_VETO_NAMES = RUNTIME_OWNED_NAMES - {"keybindings.json"}


# The scan is complete and the report is bounded. A stray tree can hold
# thousands of files, and a deploy that prints one line for each of them is
# unreadable, so converge prints this many unmanaged lines and then a tally of
# the rest. Truncating the scan itself was the other option and it is worse: a
# depth limit makes the report silently incomplete, and nothing on the line
# tells the reader that anything was left out.
UNMANAGED_REPORT_LIMIT = 50


def runtime_owned(target: str, roots: list[str]) -> bool:
    """True when a path names something Pi or one of its packages writes.

    A hard veto in front of every deletion. Deploy never lands these, so a
    manifest naming one did not come from a deploy.

    Directory names are matched only below a landing root, never against the
    absolute path: a dest of /tmp/x/agent would otherwise match `tmp` and veto
    every prune.
    """
    name = os.path.basename(target)
    if name in PRUNE_VETO_NAMES or name.endswith(".log"):
        return True
    # Both spellings. A lexical-only check misses an in-root symlink such as
    # dest/legacy -> dest/sessions, which would carry a stale row into a
    # transcript while staying physically inside the landing root.
    for candidate in (os.path.abspath(target), entry_path(target)):
        for root in roots:
            prefix = os.path.abspath(root) + os.sep
            real_prefix = os.path.realpath(root) + os.sep
            for base in (prefix, real_prefix):
                if candidate.startswith(base):
                    rel = candidate[len(base) :]
                    if any(part in RUNTIME_OWNED_DIRS for part in rel.split(os.sep)):
                        return True
    return False


def prune_mode() -> str:
    mode = os.environ.get("PI_CONFIG_PRUNE", "apply")
    if mode not in ("apply", "report", "adopt"):
        raise SystemExit(
            f"PI_CONFIG_PRUNE must be apply, report or adopt, got {mode!r}"
        )
    return mode


def _quiet_name(name: str) -> bool:
    """A name the scan never reports, at any depth."""
    return name in RUNTIME_OWNED_NAMES or name == MANIFEST_NAME or name.endswith(".log")


def _bare_dirs(candidates: list[str], files: list[str]) -> list[str]:
    """Stray directories that hold no reported file.

    A stray directory holding files is named by its files, so naming it too
    would print the same leftover twice. An empty one has no file to name it,
    and it is still a leftover a reader wants told about. The shallowest one
    wins, because a reader removes the outer directory and the rest go with it.
    """
    out: list[str] = []
    for path in sorted(candidates, key=lambda p: (p.count(os.sep), p)):
        if any(path.startswith(seen + os.sep) for seen in out):
            continue
        if any(entry.startswith(path + os.sep) for entry in files):
            continue
        out.append(path)
    return out


def unmanaged_paths(
    dest: str, landed: list[tuple[str, str]], protected: set[str]
) -> list[str]:
    """Paths under the dest that deploy did not land and Pi does not own.

    These predate the manifest, so prune cannot see them. They are reported,
    and removed only by an explicit PI_CONFIG_PRUNE=adopt run, and then only
    inside `adopt_boundary`.

    The walk has no depth limit and no file-count limit. It descends the whole
    destination, because a leftover from a writer this repository does not
    control can sit at any depth: the migration off Home Manager is exactly
    that case. Output is bounded where the printing happens, not here, so the
    answer this returns is always the whole answer.
    """
    dest_abs = os.path.abspath(dest)
    known = {os.path.realpath(path) for path, _ in landed} | protected
    files: list[str] = []
    strays: list[str] = []
    for root, dirs, names in os.walk(dest_abs, followlinks=False):
        keep = []
        for name in dirs:
            target = os.path.join(root, name)
            # Pruned from the walk rather than filtered afterwards, so a
            # session tree costs nothing to skip.
            if name in RUNTIME_OWNED_DIRS:
                continue
            if os.path.islink(target):
                # One entry, never a tree. os.walk does not follow it either,
                # so the two agree about where the destination stops.
                if not _quiet_name(name) and os.path.realpath(target) not in known:
                    files.append(target)
                continue
            keep.append(name)
            if os.path.realpath(target) not in known:
                strays.append(target)
        dirs[:] = keep
        for name in names:
            target = os.path.join(root, name)
            if _quiet_name(name):
                continue
            if os.path.realpath(target) in known:
                continue
            files.append(target)
    return sorted(set(files) | set(_bare_dirs(strays, files)))


def adopt_boundary(dest: str, landed: list[tuple[str, str]]) -> set[str]:
    """The directories `just deploy-adopt` may delete a file out of.

    The destination root, plus every directory this run landed. Nothing else.

    The scan reports at any depth and adopt does not follow it that far, and
    the reason is RUNTIME_OWNED_DIRS. That list is a fixed set of names, so a
    directory outside it is not proven safe to empty: the day Pi or one of its
    packages writes state under a name the list does not carry, a recursive
    adopt would delete that state on the next deploy. Reporting a path costs
    an operator one line. Deleting it costs them the file.
    """
    out = {os.path.realpath(dest)}
    out.update(os.path.realpath(path) for path, how in landed if how == "dir")
    return out


def within_adopt_boundary(target: str, boundary: set[str]) -> bool:
    """True when adopt may delete this path."""
    return os.path.realpath(os.path.dirname(os.path.abspath(target))) in boundary


def live_only_dests(dest: str, sidecars: list[dict[str, object]]) -> set[str]:
    out = set()
    for row in sidecars:
        if str(row["class"]) != "live-only":
            continue
        path = sidecar_dest_path(dest, row)
        if path:
            out.add(os.path.realpath(path))
    return out


def classify_stale(
    src: str, roots: list[str], target: str, how: str, protected: set[str]
) -> str:
    """Decide what to do with one path the repo no longer declares.

    First match wins. A verdict of "prune" is the only one that deletes.
    """
    real = entry_path(target)
    if os.path.realpath(target) in protected or real in protected:
        return "keep"
    # Defence in depth. The manifest is trusted state, not proof: it sits at
    # the dest, so anything able to write there could name auth.json or a
    # session for deletion. Deploy never lands these names, so a manifest row
    # carrying one is a corrupted or hand-edited file, never a real landing.
    if runtime_owned(target, roots):
        raise SystemExit(f"refusing to prune a runtime-owned path: {target}")
    src_abs = os.path.realpath(src)
    if not any(within_root(target, root) for root in roots):
        raise SystemExit(f"refusing to prune outside the landing roots: {target}")
    if real == src_abs or real.startswith(src_abs + os.sep):
        raise SystemExit(f"refusing to prune inside the clone: {target}")
    if os.path.basename(target) == MANIFEST_NAME:
        return "keep"
    if not os.path.lexists(target):
        return "gone"
    if store_owned(target):
        raise SystemExit(f"refusing to prune a store symlink: {target}")
    if how != "dir" and os.path.isdir(target) and not os.path.islink(target):
        return "refused"
    return "prune"
