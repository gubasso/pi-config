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
    """The set of paths this deploy landed, as recorded by record()."""
    run_manifest = os.environ.get("PI_CONFIG_RUN_MANIFEST")
    if not run_manifest or not os.path.isfile(run_manifest):
        raise SystemExit(
            "converge: PI_CONFIG_RUN_MANIFEST is unset or missing. "
            "A partial landing set would prune live files, so this is fatal."
        )
    rows: dict[str, str] = {}
    with open(run_manifest, encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            how, _, path = line.partition("\t")
            if not path:
                raise SystemExit(f"converge: malformed run manifest line: {line!r}")
            rows[path] = how
    return sorted(rows.items(), key=lambda kv: kv[0])


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


def record(how: str, path: str) -> None:
    """Append one landing to the run manifest deploy assembles.

    The manifest is recorded, never recomputed. A parallel enumeration would
    have to re-implement the live-only and optional-absent skips above, and
    every divergence there becomes a deletion of a file deploy never landed.

    A no-op when PI_CONFIG_RUN_MANIFEST is unset, so status and doctor are
    unaffected.
    """
    run_manifest = os.environ.get("PI_CONFIG_RUN_MANIFEST")
    if not run_manifest:
        return
    with open(run_manifest, "a", encoding="utf-8") as handle:
        handle.write(f"{how}\t{os.path.abspath(path)}\n")


def record_new_dirs(dest: str, dest_path: str) -> None:
    """Record every directory strictly under dest that dest_path needs.

    Recorded on every deploy, not only when the directory is created. A row
    that appeared only on the run that made the directory would be missing
    from the next manifest, and prune would then read it as stale.

    Only components under dest are recorded. $HOME/.pi is never one, so an
    undeclared lsp-client.json removes the file and leaves ~/.pi alone.
    """
    if not os.environ.get("PI_CONFIG_RUN_MANIFEST"):
        return
    dest_abs = os.path.abspath(dest)
    parent = os.path.dirname(os.path.abspath(dest_path))
    parts = []
    while parent.startswith(dest_abs + os.sep):
        parts.append(parent)
        parent = os.path.dirname(parent)
    for path in reversed(parts):
        record("dir", path)
