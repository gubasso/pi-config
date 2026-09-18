"""One convergence pass over the destination.

`prune` decides what may be removed and what deploy never landed. This module
is the pass that acts on those answers: it reads what this run landed, reads
what the last run landed, removes the difference, reports the rest, and writes
the new manifest.

Two removal paths meet here and they are not the same. Prune removes a path
the previous manifest recorded and the repository stopped declaring. Adopt
removes a path no manifest ever recorded, only when an operator asks for it,
and only inside `adopt_boundary`."""

from __future__ import annotations

import errno
import os

from .manifest import read_manifest, read_run_manifest, write_manifest
from .paths import landing_roots
from .prune import (
    UNMANAGED_REPORT_LIMIT,
    adopt_boundary,
    classify_stale,
    live_only_dests,
    prune_mode,
    unmanaged_paths,
    within_adopt_boundary,
)


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

    pruned += report_unmanaged(src, dest, roots, landed, protected, mode)

    if mode == "report":
        print("pi-config: report only; manifest not written")
        return
    write_manifest(src, dest, landed)
    print(f"pi-config: files converged ({len(landed)} declared, {pruned} removed)")


def report_unmanaged(
    src: str,
    dest: str,
    roots: list[str],
    landed: list[tuple[str, str]],
    protected: set[str],
    mode: str,
) -> int:
    """Name every path that predates the manifest, and adopt the ones adopt may.

    Prune cannot see these, so they are reported on every run. The line states
    which of the two cases it is, and the deletion and the sentence come from
    the same boundary, so the message cannot promise what the behavior refuses.
    """
    boundary = adopt_boundary(dest, landed)
    adopted = 0
    shown = 0
    held = 0
    for target in unmanaged_paths(dest, landed, protected):
        inside = within_adopt_boundary(target, boundary)
        if mode == "adopt" and inside:
            verdict = classify_stale(src, roots, target, "copy", protected)
            if verdict != "prune":
                print(f"  {verdict:<7} unmanaged {target}")
                continue
            os.remove(target)
            adopted += 1
            print(f"  adopted copy     {target}")
            continue
        if shown >= UNMANAGED_REPORT_LIMIT:
            held += 1
            continue
        shown += 1
        if inside:
            print(f"  unmanaged        {target} (just deploy-adopt removes it)")
        else:
            print(
                f"  unmanaged        {target}"
                " (adopt does not remove it; remove it by hand)"
            )
    if held:
        print(f"  unmanaged        ... and {held} more, not shown")
    return adopted
