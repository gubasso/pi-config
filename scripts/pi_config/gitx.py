"""The three questions this engine asks git.

Every repo-relative path here comes from paths.sidecar_repo_path, so a
filesystem access and a git query can never mean different files."""

from __future__ import annotations

import subprocess


def git_ignored(src: str, repo_rel: str) -> bool:
    """repo_rel comes from sidecar_repo_path()."""
    result = subprocess.run(
        ["git", "-C", src, "check-ignore", "-q", "--no-index", repo_rel],
        check=False,
    )
    return result.returncode == 0


def git_tracked(src: str, repo_rel: str) -> bool:
    """repo_rel comes from sidecar_repo_path()."""
    result = subprocess.run(
        ["git", "-C", src, "ls-files", "--error-unmatch", "--", repo_rel],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def git_head_bytes(src: str, repo_rel: str) -> bytes | None:
    """repo_rel comes from sidecar_repo_path()."""
    result = subprocess.run(
        ["git", "-C", src, "show", f"HEAD:{repo_rel}"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout
