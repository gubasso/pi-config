"""What a sidecar is, and whether this one is declared correctly.

The validator here is the only thing between a wrong
`docs/plugins/<name>/sidecars.json` and a wrong landing. A sensitive file
classified `symlink` would put a token into git. A runtime-written file
classified `copy` would have deploy fight the runtime on every write.

Landing lives in landing.py. This module only decides what the declaration
means.
"""

from __future__ import annotations

import json
import os

from .paths import LANDING_ROOT, plugin_docs_dir, relpath_ok

SIDECAR_CLASSES = {"live-only", "symlink", "copy"}


SIDECAR_KEYS = {
    "path",
    "class",
    "sensitive",
    "runtimeWrites",
    "required",
    "followsSymlinks",
}


def prove_json_sidecar(path: str, rel: str) -> None:
    if not rel.endswith(".json"):
        return
    try:
        value = json.load(open(path))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"sidecar {rel} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"sidecar {rel} must be a JSON object")


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
        if not rel.startswith(LANDING_ROOT):
            raise SystemExit(
                f"{path} sidecars[{i}] path must start with {LANDING_ROOT!r}. "
                "Deploy removes what the repo stops declaring, and it holds that "
                "authority only under the agent dir and ~/.pi. A package reading "
                "elsewhere needs a deliberate widening of both, in SPEC.md §9."
            )
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
