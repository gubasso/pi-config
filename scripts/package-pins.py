#!/usr/bin/env python3
"""Derive package pin metadata from source settings.json.

The pin list is the source of truth. Plugin directory names and live
tree paths are derived from each pin. Nothing is hardcoded.
"""

from __future__ import annotations

import json
import os
import re
import sys
from urllib.parse import urlparse


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


def plugin_name(source: str, kind: str, *, npm: str | None = None, git: tuple[str, str] | None = None) -> str:
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


def classify(source: str, src: str, dest: str) -> tuple[str, str, str]:
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
        path = os.path.normpath(os.path.join(src, path))
    return "local", plugin_name(source, "local"), path


def load_pins(src: str, dest: str) -> list[dict[str, str]]:
    settings = json.load(open(os.path.join(src, "settings.json")))
    raw = settings.get("packages") or []
    if not isinstance(raw, list):
        raise SystemExit("settings.json packages must be an array")
    pins = []
    seen_names: dict[str, str] = {}
    for entry in raw:
        pin = source_of(entry)
        if not pin:
            raise SystemExit("empty packages source")
        kind, name, tree = classify(pin, src, dest)
        if not name:
            raise SystemExit(f"pin {pin} produced an empty plugin name")
        if name in seen_names:
            raise SystemExit(f"duplicate plugin docs name {name} ({seen_names[name]} and {pin})")
        seen_names[name] = pin
        pins.append({"pin": pin, "name": name, "kind": kind, "tree": tree})
    return pins


def prove_docs(src: str, pins: list[dict[str, str]]) -> None:
    plugins_root = os.path.join(src, "docs", "plugins")
    names = {row["name"]: row["pin"] for row in pins}
    for row in pins:
        docs = os.path.join(plugins_root, row["name"])
        readme = os.path.join(docs, "README.md")
        spec = os.path.join(docs, "SPEC.md")
        if not os.path.isfile(readme):
            raise SystemExit(f"missing {readme} for {row['pin']}")
        if not os.path.isfile(spec):
            raise SystemExit(f"missing {spec} for {row['pin']}")
        print(f"ok  plugin docs {row['name']}")
    if os.path.isdir(plugins_root):
        for entry in sorted(os.listdir(plugins_root)):
            path = os.path.join(plugins_root, entry)
            if not os.path.isdir(path):
                continue
            if entry not in names:
                raise SystemExit(f"docs/plugins/{entry} has no matching packages pin")
    print("ok  plugin docs pairing")


def print_status(src: str, pins: list[dict[str, str]]) -> None:
    if not pins:
        print("packages none")
        return
    for row in pins:
        docs = os.path.join(src, "docs", "plugins", row["name"])
        docs_state = "yes" if os.path.isfile(os.path.join(docs, "README.md")) and os.path.isfile(os.path.join(docs, "SPEC.md")) else "no"
        tree_state = "yes" if row["tree"] and os.path.isdir(row["tree"]) else "no"
        print(f"package {row['pin']} docs {docs_state} tree {tree_state}")


def note_trees(pins: list[dict[str, str]]) -> None:
    missing = False
    for row in pins:
        if row["tree"] and os.path.isdir(row["tree"]):
            print(f"ok  package tree {row['pin']}")
            continue
        missing = True
        print(f"note: package {row['pin']} tree missing; run pi update --extensions", file=sys.stderr)
    if not missing and pins:
        print("ok  package trees")


def usage() -> None:
    raise SystemExit("usage: package-pins.py emit|prove-docs|status|note-trees SRC DEST")


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
        return
    if mode == "status":
        print_status(src, pins)
        return
    if mode == "note-trees":
        note_trees(pins)
        return
    usage()


if __name__ == "__main__":
    main()
