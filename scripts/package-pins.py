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
        os.makedirs(os.path.dirname(dest_path) or dest, exist_ok=True)
        if klass == "symlink":
            if os.path.isdir(dest_path) and not os.path.islink(dest_path):
                raise SystemExit(
                    f"refusing to replace directory {dest_path} with a symlink"
                )
            if os.path.lexists(dest_path):
                os.remove(dest_path)
            os.symlink(os.path.abspath(source_path), dest_path)
            print(f"linked {dest_path} -> {source_path}")
            continue
        if row.get("followsSymlinks") is False:
            land_atomic_sot(src, sidecar_repo_path(rel), rel, source_path, dest_path)
            continue
        if os.path.isdir(dest_path) and not os.path.islink(dest_path):
            raise SystemExit(f"refusing to replace directory {dest_path} with a copy")
        if os.path.lexists(dest_path):
            os.remove(dest_path)
        copy_regular(source_path, dest_path)
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


def usage() -> None:
    raise SystemExit(
        "usage: package-pins.py emit|prove-docs|prove-sidecars|land-sidecars|status|note-trees SRC DEST"
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
    if mode == "status":
        print_status(src, dest, pins, sidecars)
        return
    if mode == "note-trees":
        note_trees(pins)
        return
    usage()


if __name__ == "__main__":
    main()
