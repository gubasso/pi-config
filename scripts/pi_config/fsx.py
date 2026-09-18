"""Filesystem primitives, including the ones that have to be careful.

replace_with_hardlink exists for a package that opens its config with
O_NOFOLLOW and rewrites it by atomic rename: it can be given neither a
symlink nor a plain copy."""

from __future__ import annotations

import errno
import os
import shutil
import stat


def store_owned(path: str) -> bool:
    if not os.path.islink(path):
        return False
    target = os.path.realpath(path)
    return "/nix/store/" in target.replace("\\", "/")


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def write_bytes(path: str, data: bytes) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def same_inode(left: str, right: str) -> bool:
    try:
        left_stat = os.stat(left)
        right_stat = os.stat(right)
    except OSError:
        return False
    return (
        left_stat.st_dev == right_stat.st_dev and left_stat.st_ino == right_stat.st_ino
    )


def copy_regular(source_path: str, dest_path: str) -> None:
    shutil.copyfile(source_path, dest_path)
    os.chmod(dest_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)


def hardlink_supported(source_path: str, dest_dir: str) -> bool:
    """Probe the pair, because st_dev lies across btrfs subvolumes."""
    if os.stat(source_path).st_dev != os.stat(dest_dir).st_dev:
        return False
    probe = os.path.join(dest_dir, f".pi-config-link-probe.{os.getpid()}")
    try:
        os.link(source_path, probe)
    except OSError as exc:
        if exc.errno == errno.EXDEV:
            return False
        raise
    finally:
        if os.path.lexists(probe):
            os.remove(probe)
    return True


def replace_with_hardlink(source_path: str, dest_path: str) -> str:
    if os.path.isdir(dest_path) and not os.path.islink(dest_path):
        raise SystemExit(f"refusing to replace directory {dest_path} with a hardlink")
    dest_dir = os.path.dirname(dest_path) or "."
    os.makedirs(dest_dir, exist_ok=True)
    linkable = hardlink_supported(source_path, dest_dir)
    if os.path.lexists(dest_path):
        os.remove(dest_path)
    if linkable:
        os.link(source_path, dest_path)
        return "hardlinked"
    copy_regular(source_path, dest_path)
    return "copied"


def prove_nofollow_regular(path: str, rel: str) -> None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise SystemExit(
            f"dest {rel} cannot be opened without following symlinks: {exc}"
        ) from exc
    try:
        info = os.fstat(fd)
    finally:
        os.close(fd)
    if not stat.S_ISREG(info.st_mode):
        raise SystemExit(f"dest {rel} is not a regular file under O_NOFOLLOW")
