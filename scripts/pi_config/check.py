"""The source-tree contract, safe to run with no host landing at all.

A pre-commit hook calls this. It proves what a commit can break without
touching a live agent directory: the payload is complete, every pin carries
its findings, every sidecar is classified, and nothing secret is tracked.
"""

from __future__ import annotations

import subprocess

from .doctor import ok, prove_source

# Tracked here, these would be a credential or a package tree in git history.
# .gitignore already covers them; this catches the `git add -f` that ignored
# it, which .gitignore by itself cannot.
FORBIDDEN_PREFIXES = (
    "home/.pi/agent/sessions/",
    "home/.pi/agent/npm/",
    "home/.pi/agent/git/",
    "home/.pi/agent/bin/",
    "home/.pi/agent/web-search-cache/",
)

FORBIDDEN_PATHS = (
    "home/.pi/agent/auth.json",
    "home/.pi/agent/web-search.json",
    "home/.pi/agent/models.json",
    "home/.pi/agent/trust.json",
    "home/.pi/agent/models-store.json",
)


def tracked_files(src: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", src, "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def prove_no_tracked_secrets(src: str) -> None:
    for path in tracked_files(src):
        if path in FORBIDDEN_PATHS or path.startswith(FORBIDDEN_PREFIXES):
            raise SystemExit(f"tracked secret or install tree: {path}")
    ok("no tracked secrets")


def check(
    src: str,
    pins: list[dict[str, str]],
    sidecars: list[dict[str, object]],
) -> None:
    prove_source(src, pins, sidecars)
    prove_no_tracked_secrets(src)
