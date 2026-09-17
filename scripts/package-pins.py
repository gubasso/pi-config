#!/usr/bin/env python3
"""Derive package pin metadata from source settings.json.

The pin list is the source of truth. Plugin directory names, live
tree paths, and sidecar landings are derived from each pin plus
docs/plugins/<name>/sidecars.json. Nothing is hardcoded.
"""

from __future__ import annotations

import errno
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

SIDECAR_CLASSES = {"live-only", "symlink", "copy"}

# home/ mirrors $HOME, so a sidecar path states its own destination.
HOME_MIRROR = "home"
AGENT_PREFIX = ".pi/agent/"

SIDECAR_KEYS = {
    "path",
    "class",
    "sensitive",
    "runtimeWrites",
    "required",
    "followsSymlinks",
}


def source_of(entry: object) -> str:
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict) and isinstance(entry.get("source"), str):
        return entry["source"].strip()
    raise SystemExit(f"unsupported packages entry: {entry!r}")


def npm_name(spec: str) -> str:
    match = re.match(r"^(@?[^@]+(?:/[^@]+)?)(?:@(.+))?$", spec.strip())
    return match.group(1) if match else spec.strip()


def parse_git(source: str) -> tuple[str, str] | None:
    text = source.strip()
    if text.startswith("git:"):
        text = text[4:].strip()
    scp = re.match(r"^git@([^:]+):(.+)$", text)
    if scp:
        host, rest = scp.group(1), scp.group(2)
        path = rest.split("@", 1)[0].lstrip("/").removesuffix(".git")
        if host and path.count("/") >= 1:
            return host, path
        return None
    if re.match(r"^(https?|ssh|git)://", text, re.I):
        parsed = urlparse(text)
        host = parsed.hostname or ""
        path = parsed.path.lstrip("/").split("@", 1)[0].removesuffix(".git")
        if host and path.count("/") >= 1:
            return host, path
        return None
    if "/" in text and not text.startswith(("/", ".")):
        host, rest = text.split("/", 1)
        path = rest.split("@", 1)[0].removesuffix(".git")
        if (("." in host) or host == "localhost") and path.count("/") >= 1:
            return host, path
    return None


def plugin_name(
    source: str,
    kind: str,
    *,
    npm: str | None = None,
    git: tuple[str, str] | None = None,
) -> str:
    if kind == "npm":
        assert npm is not None
        return npm.lstrip("@").replace("/", "-").lower()
    if kind == "git":
        assert git is not None
        return git[1].rstrip("/").split("/")[-1].lower()
    base = os.path.basename(os.path.normpath(source))
    base = re.sub(r"\.(ts|js|mjs|cjs|json|md)$", "", base, flags=re.I)
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return slug or "package"


def frozen_ref(source: str, kind: str) -> str | None:
    """Return the version or ref this pin carries, or None when it has none.

    SPEC.md §9 makes the unversioned form the default, so any suffix here
    is a departure worth reporting. Pi itself freezes a git source on any
    ref and an npm source on an exact version, and it leaves a frozen
    source out of its startup update notice. An npm range is a departure
    from the rule without being a freeze in Pi's sense.
    """
    if kind == "npm":
        spec = source[4:].strip() if source.startswith("npm:") else source.strip()
        match = re.match(r"^(@?[^@]+(?:/[^@]+)?)@(.+)$", spec)
        return match.group(2) if match else None
    if kind == "git":
        text = source.strip()
        if text.startswith("git:"):
            text = text[4:].strip()
        text = re.sub(r"^(https?|ssh|git)://", "", text, flags=re.I)
        text = re.sub(r"^git@[^:]+:", "", text)
        head, sep, ref = text.partition("@")
        return ref.strip() if sep and ref.strip() and "/" in head else None
    return None


def classify(source: str, base: str, dest: str) -> tuple[str, str, str]:
    if source.startswith("npm:"):
        name = npm_name(source[4:])
        tree = os.path.join(dest, "npm", "node_modules", name) if dest else ""
        return "npm", plugin_name(source, "npm", npm=name), tree
    git = parse_git(source)
    if git:
        host, path = git
        tree = os.path.join(dest, "git", host, path) if dest else ""
        return "git", plugin_name(source, "git", git=git), tree
    path = source
    if not os.path.isabs(path):
        path = os.path.normpath(os.path.join(base, path))
    return "local", plugin_name(source, "local"), path


def load_pins(src: str, dest: str) -> list[dict[str, str]]:
    settings = json.load(open(os.path.join(agent_payload_dir(src), "settings.json")))
    raw = settings.get("packages") or []
    if not isinstance(raw, list):
        raise SystemExit("settings.json packages must be an array")
    pins = []
    seen_names: dict[str, str] = {}
    for entry in raw:
        pin = source_of(entry)
        if not pin:
            raise SystemExit("empty packages source")
        kind, name, tree = classify(pin, agent_payload_dir(src), dest)
        if not name:
            raise SystemExit(f"pin {pin} produced an empty plugin name")
        if name in seen_names:
            raise SystemExit(
                f"duplicate plugin docs name {name} ({seen_names[name]} and {pin})"
            )
        seen_names[name] = pin
        pins.append(
            {
                "pin": pin,
                "name": name,
                "kind": kind,
                "tree": tree,
                "frozen": frozen_ref(pin, kind) or "",
            }
        )
    return pins


def plugins_root(src: str) -> str:
    return os.path.join(src, "docs", "plugins")


def plugin_docs_dir(src: str, name: str) -> str:
    return os.path.join(plugins_root(src), name)


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


def load_plugin_sidecars(src: str, name: str, pin: str) -> list[dict[str, object]]:
    path = os.path.join(plugin_docs_dir(src, name), "sidecars.json")
    if not os.path.isfile(path):
        raise SystemExit(f"missing {path} for {pin}")
    try:
        data = json.load(open(path))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path} is not JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("sidecars"), list):
        raise SystemExit(f"{path} must be an object with a sidecars array")
    rows = []
    seen: set[str] = set()
    for i, entry in enumerate(data["sidecars"]):
        if not isinstance(entry, dict):
            raise SystemExit(f"{path} sidecars[{i}] must be an object")
        extra = set(entry) - SIDECAR_KEYS
        if extra:
            raise SystemExit(f"{path} sidecars[{i}] unknown keys: {sorted(extra)}")
        rel = entry.get("path")
        klass = entry.get("class")
        if not isinstance(rel, str) or not relpath_ok(rel):
            raise SystemExit(
                f"{path} sidecars[{i}] path must be a relative path with no .."
            )
        rel = rel.replace("\\", "/")
        if klass not in SIDECAR_CLASSES:
            raise SystemExit(
                f"{path} sidecars[{i}] class must be one of {sorted(SIDECAR_CLASSES)}"
            )
        if rel in seen:
            raise SystemExit(f"{path} duplicate sidecar path {rel}")
        seen.add(rel)
        sensitive = entry.get("sensitive", False)
        runtime = entry.get("runtimeWrites", False)
        if sensitive not in (True, False) or runtime not in (True, False):
            raise SystemExit(
                f"{path} sidecars[{i}] sensitive/runtimeWrites must be booleans"
            )
        if "required" in entry and entry["required"] not in (True, False):
            raise SystemExit(f"{path} sidecars[{i}] required must be a boolean")
        follows = entry.get("followsSymlinks", True)
        if follows not in (True, False):
            raise SystemExit(f"{path} sidecars[{i}] followsSymlinks must be a boolean")
        if klass == "live-only":
            required = False
        elif "required" in entry:
            required = bool(entry["required"])
        else:
            required = True
        if sensitive and klass != "live-only":
            raise SystemExit(
                f"{path} sidecars[{i}] sensitive files must be class live-only"
            )
        if follows is False and klass != "copy":
            raise SystemExit(
                f"{path} sidecars[{i}] followsSymlinks false requires class copy"
            )
        if runtime and klass == "copy" and follows is not False:
            raise SystemExit(
                f"{path} sidecars[{i}] runtimeWrites files must be class symlink unless followsSymlinks is false"
            )
        if klass == "symlink" and follows is False:
            raise SystemExit(
                f"{path} sidecars[{i}] cannot symlink when followsSymlinks is false"
            )
        rows.append(
            {
                "plugin": name,
                "pin": pin,
                "path": rel,
                "class": klass,
                "sensitive": bool(sensitive),
                "runtimeWrites": bool(runtime),
                "required": required,
                "followsSymlinks": bool(follows),
            }
        )
    return rows


def load_sidecars(src: str, pins: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen_paths: dict[str, str] = {}
    for pin in pins:
        for row in load_plugin_sidecars(src, pin["name"], pin["pin"]):
            rel = str(row["path"])
            if rel in seen_paths:
                raise SystemExit(
                    f"duplicate sidecar path {rel} ({seen_paths[rel]} and {row['pin']})"
                )
            seen_paths[rel] = str(row["pin"])
            rows.append(row)
    return rows


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


def store_owned(path: str) -> bool:
    if not os.path.islink(path):
        return False
    target = os.path.realpath(path)
    return "/nix/store/" in target.replace("\\", "/")


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


def prove_json_sidecar(path: str, rel: str) -> None:
    if not rel.endswith(".json"):
        return
    try:
        value = json.load(open(path))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"sidecar {rel} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"sidecar {rel} must be a JSON object")


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


def prove_docs(src: str, pins: list[dict[str, str]]) -> None:
    root = plugins_root(src)
    names = {row["name"]: row["pin"] for row in pins}
    for row in pins:
        docs = plugin_docs_dir(src, row["name"])
        for name in ("README.md", "SPEC.md", "sidecars.json"):
            path = os.path.join(docs, name)
            if not os.path.isfile(path):
                raise SystemExit(f"missing {path} for {row['pin']}")
        print(f"ok  plugin docs {row['name']}")
    if os.path.isdir(root):
        for entry in sorted(os.listdir(root)):
            path = os.path.join(root, entry)
            if not os.path.isdir(path):
                continue
            if entry not in names:
                raise SystemExit(f"docs/plugins/{entry} has no matching packages pin")
    print("ok  plugin docs pairing")
    note_frozen(pins)


def note_frozen(pins: list[dict[str, str]]) -> None:
    """Report pins that carry a version or ref. A freeze is allowed, with a reason."""
    frozen = [row for row in pins if row["frozen"]]
    for row in frozen:
        print(
            f"note: pin {row['pin']} carries {row['frozen']}, and the default"
            " is unversioned. Keep it only to hold back a known-bad upstream,"
            " and say in the commit message what removes it"
            " (docs/guides/package-pinning.md)",
            file=sys.stderr,
        )
    if not frozen:
        print("ok  pins unversioned")


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


def print_status(
    src: str, dest: str, pins: list[dict[str, str]], sidecars: list[dict[str, object]]
) -> None:
    if not pins:
        print("packages none")
        return
    for row in pins:
        docs = plugin_docs_dir(src, row["name"])
        docs_state = (
            "yes"
            if all(
                os.path.isfile(os.path.join(docs, name))
                for name in ("README.md", "SPEC.md", "sidecars.json")
            )
            else "no"
        )
        tree_state = "yes" if row["tree"] and os.path.isdir(row["tree"]) else "no"
        pin_state = f"frozen {row['frozen']}" if row["frozen"] else "unversioned"
        print(f"package {row['pin']} docs {docs_state} tree {tree_state} {pin_state}")
    for row in sidecars:
        rel = str(row["path"])
        dest_path = sidecar_dest_path(dest, row)
        if dest_path and os.path.islink(dest_path):
            state = "symlink"
        elif dest_path and os.path.isfile(dest_path):
            source_path = sidecar_source_path(src, rel)
            state = "hardlink" if same_inode(source_path, dest_path) else "file"
        else:
            state = "no"
        print(f"sidecar {rel} class {row['class']} dest {state}")


def note_trees(pins: list[dict[str, str]]) -> None:
    missing = False
    for row in pins:
        if row["tree"] and os.path.isdir(row["tree"]):
            print(f"ok  package tree {row['pin']}")
            continue
        missing = True
        print(
            f"note: package {row['pin']} tree missing; run pi update --extensions",
            file=sys.stderr,
        )
    if not missing and pins:
        print("ok  package trees")


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
    write_bytes(manifest_path(dest), body.encode("utf-8"))


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
    pi_home = os.path.join(os.path.expanduser("~"), ".pi")
    for row in rows:
        target, how = row["path"], row["how"]
        if not (
            target.startswith(dest_abs + os.sep) or target.startswith(pi_home + os.sep)
        ):
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
}


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
    src: str, dest: str, target: str, how: str, protected: set[str]
) -> str:
    """Decide what to do with one path the repo no longer declares.

    First match wins. A verdict of "prune" is the only one that deletes.
    """
    real = os.path.realpath(target)
    if real in protected:
        return "keep"
    dest_abs = os.path.abspath(dest)
    pi_home = os.path.join(os.path.expanduser("~"), ".pi")
    src_abs = os.path.realpath(src)
    inside = target.startswith(dest_abs + os.sep) or target.startswith(pi_home + os.sep)
    if not inside or target in (dest_abs, pi_home, os.path.expanduser("~")):
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
    keep = {os.path.realpath(path) for path, _ in landed}
    protected = live_only_dests(dest, sidecars)

    stale = [row for row in old if os.path.realpath(row["path"]) not in keep]
    verdicts = [
        (
            row["path"],
            row["how"],
            classify_stale(src, dest, row["path"], row["how"], protected),
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

    if mode == "apply":
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
            verdict = classify_stale(src, dest, target, "copy", protected)
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


def installed_npm(dest: str) -> dict[str, str]:
    """Packages npm has installed, read from the project manifest Pi maintains.

    Not a node_modules listing: that tree is one flat npm project holding
    every transitive dependency, so a directory scan reports dozens of false
    orphans. A dependency key is already `@scope/name`.
    """
    path = os.path.join(dest, "npm", "package.json")
    if not os.path.isfile(path):
        return {}
    try:
        data = json.load(open(path, encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    deps = data.get("dependencies")
    return dict(deps) if isinstance(deps, dict) else {}


def installed_git(dest: str) -> dict[str, str]:
    """Git clones under dest/git, keyed by the pin source that installed them."""
    root = os.path.join(dest, "git")
    out: dict[str, str] = {}
    if not os.path.isdir(root):
        return out
    for current, dirs, _ in os.walk(root):
        if ".git" in dirs or os.path.isdir(os.path.join(current, ".git")):
            rel = os.path.relpath(current, root).replace(os.sep, "/")
            out[f"git:{rel}"] = current
            dirs[:] = []
    return out


def pi_remove(source: str) -> tuple[int, str]:
    result = subprocess.run(
        ["pi", "remove", source],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def converge_trees(dest: str, pins: list[dict[str, str]]) -> None:
    """Remove an install tree whose pin has left settings.json.

    Always through `pi remove`. dest/npm is one real npm project with a
    package.json and a lockfile, so deleting a directory by hand leaves the
    dependency entry behind and the next install resurrects the tree.
    """
    declared_npm = {npm_name(row["pin"][4:]) for row in pins if row["kind"] == "npm"}
    declared_git = {row["pin"] for row in pins if row["kind"] == "git"}

    orphans: list[tuple[str, str]] = []
    for name in sorted(installed_npm(dest)):
        if name not in declared_npm:
            orphans.append((f"npm:{name}", "npm"))
    for source, tree in sorted(installed_git(dest).items()):
        if source not in declared_git and os.path.realpath(tree) not in {
            os.path.realpath(row["tree"]) for row in pins if row["tree"]
        }:
            orphans.append((source, "git"))

    print(
        f"pi-config: converging install trees ({len(pins)} pinned, {len(orphans)} orphaned)"
    )
    if not orphans:
        return
    for source, kind in orphans:
        print(f"  prune   {kind:<8} {source}")

    if prune_mode() == "report":
        print("pi-config: report only; no tree removed")
        return
    if not shutil.which("pi"):
        print(
            "note: pi is not on PATH; run pi remove for each orphan above",
            file=sys.stderr,
        )
        return

    for source, _ in orphans:
        code, output = pi_remove(source)
        # removeAndPersist uninstalls the tree first, then finds the pin
        # already gone from settings and exits 1. That is this exact case.
        if code == 1 and "No matching package found" in output:
            print(f'note: pi exited 1 with "No matching package found" for {source}')
        elif code != 0:
            raise SystemExit(f"pi remove {source} failed ({code}):\n{output}")
        if source.startswith("npm:") and source[4:] in installed_npm(dest):
            raise SystemExit(f"pi remove {source} left the dependency in place")
        print(f"removed tree {source}")


def usage() -> None:
    raise SystemExit(
        "usage: package-pins.py emit|prove-docs|prove-sidecars|land-sidecars|converge|converge-trees|prove-manifest|status|note-trees SRC DEST"
    )


def main() -> None:
    if len(sys.argv) != 4:
        usage()
    mode, src, dest = sys.argv[1], sys.argv[2], sys.argv[3]
    pins = load_pins(src, dest)
    if mode == "emit":
        for row in pins:
            json.dump(row, sys.stdout)
            sys.stdout.write("\n")
        return
    if mode == "prove-docs":
        prove_docs(src, pins)
        load_sidecars(src, pins)
        return
    sidecars = load_sidecars(src, pins) if mode != "note-trees" else []
    if mode == "prove-sidecars":
        prove_docs(src, pins)
        prove_sidecars_source(src, sidecars)
        if os.environ.get("DOCTOR_SOURCE_ONLY") == "1":
            return
        if not os.path.isdir(dest):
            print(f"note: dest {dest} does not exist (source-only sidecars)")
            return
        prove_sidecars_landing(src, dest, sidecars)
        return
    if mode == "land-sidecars":
        land_sidecars(src, dest, sidecars)
        return
    if mode == "converge":
        converge(src, dest, sidecars)
        return
    if mode == "prove-manifest":
        prove_manifest(src, dest)
        return
    if mode == "converge-trees":
        converge_trees(dest, pins)
        return
    if mode == "status":
        print_status(src, dest, pins, sidecars)
        return
    if mode == "note-trees":
        note_trees(pins)
        return
    usage()


if __name__ == "__main__":
    main()
