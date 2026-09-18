"""Where a path is, and whether it is allowed to be there.

No filesystem writes and no policy beyond containment. landing_roots and
within_root are what bound every deletion the engine performs."""

from __future__ import annotations

import os

# home/ mirrors $HOME, so a sidecar path states its own destination.
HOME_MIRROR = "home"


AGENT_PREFIX = ".pi/agent/"


# Every sidecar path is $HOME-relative and must stay under this prefix, which
# bounds deploy's landing roots to the agent dir and ~/.pi. Prune derives its
# authority from those two, so widening this widens what deploy may delete.
LANDING_ROOT = ".pi/"


def relpath_ok(path: str) -> bool:
    if not path or path.startswith("/") or path.startswith("\\"):
        return False
    parts = path.replace("\\", "/").split("/")
    return all(p and p not in (".", "..") for p in parts)


def sidecar_repo_path(rel: str) -> str:
    """The one repo-relative path for a sidecar.

    Every filesystem access and every `git -C src` call for a sidecar goes
    through this, so the two can never disagree about which file they mean.
    """
    return f"{HOME_MIRROR}/{rel}"


def sidecar_source_path(src: str, rel: str) -> str:
    return os.path.join(src, *sidecar_repo_path(rel).split("/"))


def sidecar_dest_path(dest: str, row: dict[str, object]) -> str:
    """A path under .pi/agent/ follows PI_CODING_AGENT_DIR. Anything else is $HOME."""
    rel = str(row["path"])
    if rel.startswith(AGENT_PREFIX):
        if not dest:
            return ""
        return os.path.join(dest, *rel[len(AGENT_PREFIX) :].split("/"))
    return os.path.join(os.path.expanduser("~"), *rel.split("/"))


def agent_payload_dir(src: str) -> str:
    return os.path.join(src, HOME_MIRROR, ".pi", "agent")


def plugins_root(src: str) -> str:
    return os.path.join(src, "docs", "plugins")


def plugin_docs_dir(src: str, name: str) -> str:
    return os.path.join(plugins_root(src), name)


def entry_path(path: str) -> str:
    """The physical location of a directory entry, without resolving its leaf.

    os.remove and os.rmdir resolve intermediate symlinks but act on the final
    component itself, so containment must be judged the same way. Resolving
    the leaf would report a symlink's target, which for a deployed symlink is
    a file inside the clone.
    """
    parent = os.path.realpath(os.path.dirname(os.path.abspath(path)))
    return os.path.join(parent, os.path.basename(path))


def landing_roots(dest: str) -> list[str]:
    """The only two roots deploy may write under, as policy, not as data.

    Derived here and never read back from the manifest. Roots stored beside
    the paths they authorize would be circular: editing one field of an
    untrusted document would licence deleting anything it named. LANDING_ROOT
    is what keeps a sidecar path inside these two.

    A root that is itself a symlink is fatal. Both halves of within_root move
    with it, so a swapped root would silently redirect every landing and every
    deletion to wherever it points.
    """
    roots = [os.path.abspath(dest), os.path.abspath(os.path.expanduser("~/.pi"))]
    for root in roots:
        if os.path.islink(root):
            raise SystemExit(
                f"landing root {root} is a symlink; refusing to land or prune through it"
            )
    return roots


def within_root(target: str, root: str) -> bool:
    """True when target lies under root both lexically and physically.

    Both must hold. The lexical test stops a swapped root directory from
    redirecting deletions somewhere else; the physical test stops a swapped
    intermediate directory from doing the same.
    """
    lexical = os.path.abspath(target).startswith(os.path.abspath(root) + os.sep)
    physical = entry_path(target).startswith(os.path.realpath(root) + os.sep)
    return lexical and physical
