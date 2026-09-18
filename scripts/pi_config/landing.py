"""Putting a classified sidecar where it belongs, and proving it landed.

Three classes land three ways. `live-only` is never touched, because it can
hold a token. `symlink` points the destination at the source, so the runtime
writes through to git. `copy` puts this repository's bytes at the
destination, and for a package that refuses symlinks it becomes a hardlink
kept in step by a 3-way merge.
"""

from __future__ import annotations

import os

from .fsx import (
    copy_regular,
    hardlink_supported,
    prove_nofollow_regular,
    read_bytes,
    replace_with_hardlink,
    same_inode,
    store_owned,
    write_bytes,
)
from .gitx import git_head_bytes, git_ignored, git_tracked
from .manifest import record, record_new_dirs
from .paths import (
    landing_roots,
    sidecar_dest_path,
    sidecar_repo_path,
    sidecar_source_path,
    within_root,
)
from .sidecars import prove_json_sidecar


def land_atomic_sot(
    src: str, repo_rel: str, rel: str, source_path: str, dest_path: str
) -> None:
    source_bytes = read_bytes(source_path)
    dest_exists = os.path.isfile(dest_path) and not os.path.islink(dest_path)
    dest_bytes = read_bytes(dest_path) if dest_exists else None
    # base is None when the path is absent from HEAD: a newly authored sidecar,
    # or one staged but not yet committed. The merge below then has no base and
    # falls through to the conflict message, which names that case.
    base = git_head_bytes(src, repo_rel)
    if dest_bytes is None or dest_bytes == source_bytes:
        kind = replace_with_hardlink(source_path, dest_path)
        print(f"{kind} {dest_path}")
        return
    if base is not None and dest_bytes == base and source_bytes != base:
        kind = replace_with_hardlink(source_path, dest_path)
        print(f"{kind} {dest_path} (pushed source)")
        return
    if base is not None and source_bytes == base and dest_bytes != base:
        write_bytes(source_path, dest_bytes)
        kind = replace_with_hardlink(source_path, dest_path)
        print(f"imported {rel} dest -> source; {kind} {dest_path}")
        return
    raise SystemExit(
        f"sidecar {rel} conflict: source and dest differ"
        + (" from HEAD" if base is not None else " and the file is not in HEAD")
        + ". Copy the winner onto the other path, then just deploy."
    )


def prove_sidecars_source(src: str, sidecars: list[dict[str, object]]) -> None:
    for row in sidecars:
        rel = str(row["path"])
        klass = str(row["class"])
        repo_rel = sidecar_repo_path(rel)
        source_path = sidecar_source_path(src, rel)
        if klass == "live-only":
            if os.path.lexists(source_path):
                raise SystemExit(f"live-only sidecar must not exist in source: {rel}")
            if git_tracked(src, repo_rel):
                raise SystemExit(f"live-only sidecar is tracked: {rel}")
            if not git_ignored(src, repo_rel):
                raise SystemExit(f"live-only sidecar is not gitignored: {rel}")
            print(f"ok  sidecar live-only {rel}")
            continue
        if git_ignored(src, repo_rel):
            raise SystemExit(f"{klass} sidecar is gitignored: {rel}")
        if row["required"] and not os.path.isfile(source_path):
            raise SystemExit(f"missing source sidecar {rel} for {row['pin']}")
        if os.path.lexists(source_path) and not os.path.isfile(source_path):
            raise SystemExit(f"source sidecar {rel} is not a regular file")
        if os.path.isfile(source_path):
            # Present but untracked passes every local gate and is absent
            # from the commit, so a fresh clone cannot deploy. .gitignore
            # cannot catch this: the file is neither ignored nor added.
            if not git_tracked(src, repo_rel):
                raise SystemExit(
                    f"{klass} sidecar {rel} exists but is untracked; git add it"
                )
            prove_json_sidecar(source_path, rel)
            print(f"ok  sidecar source {klass} {rel}")
        else:
            print(f"ok  sidecar optional-absent {klass} {rel}")


def prove_sidecars_landing(
    src: str, dest: str, sidecars: list[dict[str, object]]
) -> None:
    for row in sidecars:
        rel = str(row["path"])
        klass = str(row["class"])
        source_path = sidecar_source_path(src, rel)
        dest_path = sidecar_dest_path(dest, row)
        if klass == "live-only":
            if os.path.islink(dest_path):
                raise SystemExit(f"live-only sidecar {rel} is a symlink at dest")
            if store_owned(dest_path):
                raise SystemExit(f"live-only sidecar {rel} is a store symlink")
            print(f"ok  sidecar dest live-only {rel}")
            continue
        if not os.path.isfile(source_path):
            if row["required"]:
                raise SystemExit(f"missing source sidecar {rel}")
            print(f"ok  sidecar dest optional-absent {rel}")
            continue
        if klass == "symlink":
            if not os.path.islink(dest_path):
                raise SystemExit(f"dest {rel} is not a symlink")
            if store_owned(dest_path):
                raise SystemExit(f"dest {rel} is a store symlink")
            if os.path.realpath(dest_path) != os.path.realpath(source_path):
                raise SystemExit(
                    f"dest {rel} -> {os.path.realpath(dest_path)}, want {os.path.realpath(source_path)}"
                )
            print(f"ok  sidecar dest symlink {rel}")
            continue
        if os.path.islink(dest_path) or not os.path.isfile(dest_path):
            raise SystemExit(f"dest {rel} is not a regular file")
        if store_owned(dest_path):
            raise SystemExit(f"dest {rel} is a store symlink")
        if read_bytes(source_path) != read_bytes(dest_path):
            raise SystemExit(f"dest {rel} does not match source")
        if row.get("followsSymlinks") is False:
            prove_nofollow_regular(dest_path, rel)
            dest_dir = os.path.dirname(dest_path) or dest
            if not hardlink_supported(source_path, dest_dir):
                print(f"ok  sidecar dest copy {rel} (cross-device; no hardlink)")
                continue
            if not same_inode(source_path, dest_path):
                raise SystemExit(
                    f"dest {rel} is not a hardlink to source (atomic replace broke it); run just deploy"
                )
            print(f"ok  sidecar dest hardlink {rel}")
            continue
        print(f"ok  sidecar dest copy {rel}")


def land_sidecars(src: str, dest: str, sidecars: list[dict[str, object]]) -> None:
    os.makedirs(dest, exist_ok=True)
    for row in sidecars:
        rel = str(row["path"])
        klass = str(row["class"])
        source_path = sidecar_source_path(src, rel)
        dest_path = sidecar_dest_path(dest, row)
        if klass == "live-only":
            continue
        if not os.path.isfile(source_path):
            if row["required"]:
                raise SystemExit(f"missing source sidecar {rel}")
            continue
        if store_owned(dest_path):
            raise SystemExit(f"Home Manager still owns {dest_path} (store symlink).")
        # A sidecar path is validated as relative and under .pi/, but that
        # says nothing about the destination. Replace an intermediate
        # directory such as `intercom` with a symlink and every landing
        # below it goes wherever the link points. within_root judges the
        # entry both lexically and physically, so the physical half is what
        # catches exactly that.
        if not any(within_root(dest_path, root) for root in landing_roots(dest)):
            raise SystemExit(
                f"refusing to land {rel} outside the landing roots: {dest_path}"
            )
        record_new_dirs(dest, dest_path)
        os.makedirs(os.path.dirname(dest_path) or dest, exist_ok=True)
        if klass == "symlink":
            if os.path.isdir(dest_path) and not os.path.islink(dest_path):
                raise SystemExit(
                    f"refusing to replace directory {dest_path} with a symlink"
                )
            if os.path.lexists(dest_path):
                os.remove(dest_path)
            os.symlink(os.path.abspath(source_path), dest_path)
            record("symlink", dest_path)
            print(f"linked {dest_path} -> {source_path}")
            continue
        if row.get("followsSymlinks") is False:
            land_atomic_sot(src, sidecar_repo_path(rel), rel, source_path, dest_path)
            record("copy", dest_path)
            continue
        if os.path.isdir(dest_path) and not os.path.islink(dest_path):
            raise SystemExit(f"refusing to replace directory {dest_path} with a copy")
        if os.path.lexists(dest_path):
            os.remove(dest_path)
        copy_regular(source_path, dest_path)
        record("copy", dest_path)
        print(f"copied {dest_path}")
