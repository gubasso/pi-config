"""Reading the `packages` array: which upstream, under which name, frozen or not."""

from __future__ import annotations

import json
import os
import re
import sys
from urllib.parse import urlparse

from .paths import agent_payload_dir, plugin_docs_dir, plugins_root


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


def prove_docs(src: str, pins: list[dict[str, str]], quiet: bool = False) -> None:
    """Every pin has its docs, and every docs directory has its pin.

    `quiet` proves without narrating. Deploy's preflight runs this before it
    writes, and doctor runs it again after, so the second run is the one the
    operator reads.
    """
    root = plugins_root(src)
    names = {row["name"]: row["pin"] for row in pins}
    for row in pins:
        docs = plugin_docs_dir(src, row["name"])
        for name in ("README.md", "SPEC.md", "sidecars.json"):
            path = os.path.join(docs, name)
            if not os.path.isfile(path):
                raise SystemExit(f"missing {path} for {row['pin']}")
        if not quiet:
            print(f"ok  plugin docs {row['name']}")
    if os.path.isdir(root):
        for entry in sorted(os.listdir(root)):
            path = os.path.join(root, entry)
            if not os.path.isdir(path):
                continue
            if entry not in names:
                raise SystemExit(f"docs/plugins/{entry} has no matching packages pin")
    if not quiet:
        print("ok  plugin docs pairing")
    note_frozen(pins, quiet=quiet)


def note_frozen(pins: list[dict[str, str]], quiet: bool = False) -> None:
    """Report pins that carry a version or ref. A freeze is allowed, with a reason.

    A frozen pin is a note rather than a failure, so `quiet` silences it too.
    Doctor repeats the note after the landing.
    """
    if quiet:
        return
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
