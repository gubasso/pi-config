"""Removing what the repo stopped declaring, and refusing everything else.

The manifest is trusted state, not proof. It sits at the destination, so
anything able to write there could name auth.json for deletion. The veto
here is what stands behind it."""

from __future__ import annotations

import errno
import os

from .fsx import store_owned
from .manifest import MANIFEST_NAME, read_manifest, read_run_manifest, write_manifest
from .paths import entry_path, landing_roots, sidecar_dest_path, within_root

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


def unmanaged_paths(
    dest: str, landed: list[tuple[str, str]], protected: set[str]
) -> list[str]:
    """Files at the dest that deploy did not land and Pi does not own.

    These predate the manifest, so prune cannot see them. They are reported,
    and removed only by an explicit PI_CONFIG_PRUNE=adopt run.
    """
    dest_abs = os.path.abspath(dest)
    known = {os.path.realpath(path) for path, _ in landed} | protected
    managed_dirs = [path for path, how in landed if how == "dir"]
    roots = [dest_abs] + managed_dirs
    out = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            target = os.path.join(root, name)
            if name in RUNTIME_OWNED_NAMES or name == MANIFEST_NAME:
                continue
            if name.endswith(".log"):
                continue
            if name in RUNTIME_OWNED_DIRS and os.path.isdir(target):
                continue
            if os.path.isdir(target) and not os.path.islink(target):
                continue
            if os.path.realpath(target) in known:
                continue
            out.append(target)
    return sorted(set(out))


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


def converge(src: str, dest: str, sidecars: list[dict[str, object]]) -> None:
    """Land the recorded set, then remove what the repo no longer declares."""
    mode = prune_mode()
    landed = read_run_manifest()
    old = read_manifest(dest)
    roots = landing_roots(dest)
    keep = {os.path.realpath(path) for path, _ in landed}
    protected = live_only_dests(dest, sidecars)

    stale = [row for row in old if os.path.realpath(row["path"]) not in keep]
    verdicts = [
        (
            row["path"],
            row["how"],
            classify_stale(src, roots, row["path"], row["how"], protected),
        )
        for row in stale
    ]

    pruned = 0
    print(f"pi-config: converging files ({len(landed)} declared, {len(stale)} stale)")
    for target, how, verdict in verdicts:
        if verdict == "keep":
            continue
        if verdict == "gone":
            print(f"  gone    {how:<8} {target}")
            continue
        if verdict == "refused":
            print(f"  refused {how:<8} {target} (now a directory)")
            continue
        if mode == "report":
            print(f"  would-prune {how:<8} {target}")
            continue
        print(f"  prune   {how:<8} {target}")

    if mode in ("apply", "adopt"):
        for target, how, verdict in verdicts:
            if verdict != "prune" or how == "dir":
                continue
            os.remove(target)
            pruned += 1
        # Deepest first, so a nested pair empties before its parent.
        dirs = sorted(
            (t for t, how, v in verdicts if v == "prune" and how == "dir"),
            key=lambda p: p.count(os.sep),
            reverse=True,
        )
        for target in dirs:
            try:
                os.rmdir(target)
                pruned += 1
            except OSError as exc:
                if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST, errno.ENOTDIR):
                    raise
                print(f"  kept    not-empty {target}")

    # Files that predate the manifest. Prune cannot see them, so they are
    # reported every run and removed only by an explicit adopt.
    unmanaged = unmanaged_paths(dest, landed, protected)
    for target in unmanaged:
        if mode == "adopt":
            verdict = classify_stale(src, roots, target, "copy", protected)
            if verdict != "prune":
                print(f"  {verdict:<7} unmanaged {target}")
                continue
            os.remove(target)
            pruned += 1
            print(f"  adopted copy     {target}")
        else:
            print(f"  unmanaged        {target} (just deploy-adopt removes it)")

    if mode == "report":
        print("pi-config: report only; manifest not written")
        return
    write_manifest(src, dest, landed)
    print(f"pi-config: files converged ({len(landed)} declared, {pruned} removed)")
