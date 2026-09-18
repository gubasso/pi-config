"""The deploy manifest: what a run landed, recorded as it lands.

Recorded, never recomputed. A parallel enumeration would have to repeat
every skip rule in sidecars, and a divergence there deletes a file deploy
never landed. Reading it never guesses: an unfamiliar manifest means no
prune this run."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

from .fsx import store_owned
from .paths import landing_roots, within_root

MANIFEST_NAME = ".pi-config-manifest.json"


MANIFEST_VERSION = 1


def manifest_path(dest: str) -> str:
    return os.path.join(dest, MANIFEST_NAME)


def read_run_manifest() -> list[tuple[str, str]]:
    """What this deploy landed, refusing an empty set.

    An empty set means the landing did not happen, and converge would read
    every path in the previous manifest as stale and remove it. Failing here
    costs a re-run; the alternative costs the live agent directory.
    """
    rows = landed()
    if not rows:
        raise SystemExit(
            "converge: this run landed nothing. A partial landing set would "
            "prune live files, so this is fatal."
        )
    return rows


def read_manifest(dest: str) -> list[dict[str, str]]:
    """The previous deploy's paths. Missing or unreadable yields an empty list."""
    path = manifest_path(dest)
    if not os.path.isfile(path):
        return []
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"note: {path} unreadable ({exc}); no prune this run", file=sys.stderr)
        return []
    if not isinstance(data, dict) or data.get("version") != MANIFEST_VERSION:
        print(
            f"note: {path} is not version {MANIFEST_VERSION}; no prune this run",
            file=sys.stderr,
        )
        return []
    rows = data.get("paths")
    if not isinstance(rows, list):
        print(f"note: {path} has no paths array; no prune this run", file=sys.stderr)
        return []
    out = []
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("path"), str):
            out.append({"path": row["path"], "how": str(row.get("how") or "copy")})
    return out


def write_manifest(src: str, dest: str, landed: list[tuple[str, str]]) -> None:
    payload = {
        "version": MANIFEST_VERSION,
        "deployedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": os.path.abspath(src),
        "paths": [{"path": path, "how": how} for path, how in landed],
    }
    body = json.dumps(payload, indent=2) + "\n"
    write_manifest_bytes(manifest_path(dest), body.encode("utf-8"))


def write_manifest_bytes(path: str, data: bytes) -> None:
    """Replace the manifest entry, never write through it.

    `open(path, "wb")` follows a trailing symlink and truncates its target, so
    a planted or leftover `.pi-config-manifest.json` symlink would destroy
    whatever it points at. Writing a fresh regular file and calling os.replace
    swaps the directory entry instead, and leaves no truncated manifest when
    the write fails.
    """
    if os.path.islink(path):
        raise SystemExit(f"refusing to write the manifest through a symlink: {path}")
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".pi-config-manifest.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.lexists(tmp):
            os.remove(tmp)
        raise


def prove_manifest(src: str, dest: str) -> None:
    """Prove the deployed extent matches the manifest.

    Content is already proved by doctor and prove_sidecars_landing. This
    proves extent: that every path deploy recorded is still there, in the
    shape deploy left it.
    """
    path = manifest_path(dest)
    if not os.path.isfile(path):
        print(f"note: no deploy manifest at {dest}; run just deploy")
        return
    rows = read_manifest(dest)
    if not rows:
        raise SystemExit(f"{path} carries no usable paths")

    dest_abs = os.path.abspath(dest)
    roots = landing_roots(dest)
    for row in rows:
        target, how = row["path"], row["how"]
        if not any(within_root(target, root) for root in roots):
            raise SystemExit(f"manifest path escapes the landing roots: {target}")
        if how == "dir":
            if not os.path.isdir(target):
                raise SystemExit(f"manifest dir missing: {target}")
        elif how == "symlink":
            if not os.path.islink(target):
                raise SystemExit(f"manifest symlink missing: {target}")
            if store_owned(target):
                raise SystemExit(f"manifest symlink is store-owned: {target}")
        elif not os.path.isfile(target) or os.path.islink(target):
            raise SystemExit(f"manifest copy missing or not a regular file: {target}")

    # Coverage, the direction that catches a landing site added without a
    # record call. These three are unconditional in deploy, so a manifest
    # that omits any of them means the run file was incomplete.
    recorded = {row["path"] for row in rows}
    for expected in ("AGENTS.md", "prompts/review.md", "settings.json"):
        target = os.path.join(dest_abs, *expected.split("/"))
        if target not in recorded:
            raise SystemExit(
                f"manifest does not record {expected}; a landing went unrecorded"
            )

    # A moved or worktree clone is legal, so this is a note, never a failure.
    written_by = manifest_source(dest)
    if written_by and os.path.abspath(written_by) != os.path.abspath(src):
        print(f"note: manifest was written by {written_by}", file=sys.stderr)
    print(f"ok  deployed extent ({len(rows)} paths)")


def manifest_source(dest: str) -> str:
    try:
        data = json.load(open(manifest_path(dest), encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    return str(data.get("source") or "") if isinstance(data, dict) else ""


# What this deploy has landed so far, path to how.
#
# One process does the whole landing now, so this is a dictionary rather than
# the tab-delimited temp file bash and Python once passed between them. The
# rule it serves is unchanged: the manifest is recorded as a side effect of
# landing, never recomputed. A parallel enumeration would have to repeat every
# live-only and optional-absent skip in landing.py, and each divergence there
# deletes a file deploy never landed.
_LANDED: dict[str, str] = {}


def reset_landed() -> None:
    """Start a new deploy. Called once, before anything lands."""
    _LANDED.clear()


def record(how: str, path: str) -> None:
    """Note that this run landed one path, and how."""
    _LANDED[os.path.abspath(path)] = how


def landed() -> list[tuple[str, str]]:
    """Everything this run landed, in path order."""
    return sorted(_LANDED.items())


def record_new_dirs(dest: str, dest_path: str) -> None:
    """Record every directory strictly under dest that dest_path needs.

    Recorded on every deploy, not only when the directory is created. A row
    that appeared only on the run that made the directory would be missing
    from the next manifest, and prune would then read it as stale.

    Only components under dest are recorded. $HOME/.pi is never one, so an
    undeclared lsp-client.json removes the file and leaves ~/.pi alone.
    """
    dest_abs = os.path.abspath(dest)
    parent = os.path.dirname(os.path.abspath(dest_path))
    parts = []
    while parent.startswith(dest_abs + os.sep):
        parts.append(parent)
        parent = os.path.dirname(parent)
    for path in reversed(parts):
        record("dir", path)
