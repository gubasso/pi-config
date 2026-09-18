"""Proving the source tree, and the landing when a destination exists.

Two halves. The source half needs no host landing at all, which is what lets
a pre-commit hook run it through `just check`. The destination half runs
after a deploy and proves the landing matches what the repository declares.

Every failure here raises. A proof that warns is a proof nobody reads.
"""

from __future__ import annotations

import json
import os
import stat

from .fsx import store_owned
from .gitx import git_ignored
from .landing import prove_sidecars_landing, prove_sidecars_source
from .manifest import prove_manifest
from .paths import agent_payload_dir
from .pins import prove_docs
from .trees import note_trees

# Files the repository cannot work without. A missing one is a broken clone,
# not a state to converge.
REQUIRED_META = (
    "SPEC.md",
    "README.md",
    "AGENTS.md",
    "justfile",
    ".gitignore",
    "package.json",
    "flake.nix",
    ".envrc",
    ".pre-commit-config.yaml",
)

REQUIRED_PAYLOAD = (
    ".pi/agent/settings.json",
    ".pi/agent/AGENTS.md",
    ".pi/agent/prompts/review.md",
    ".pi/agent/extensions/worktree-guard.ts",
    ".pi/lsp-client.json",
)

# The never-commit list, as .gitignore must spell it. Two files carry this
# rule and tests/meta keeps them in step.
REQUIRED_IGNORES = (
    "/home/.pi/agent/auth.json",
    "/home/.pi/agent/web-search.json",
    "/home/.pi/agent/web-search-cache/",
    "/home/.pi/agent/sessions/",
    "/home/.pi/agent/npm/",
    "/home/.pi/agent/git/",
    "/home/.pi/agent/bin/",
    "/home/.pi/agent/models.json",
    "/home/.pi/agent/trust.json",
    "/home/.pi/agent/intercom/broker.port.json",
)

# Proved through git rather than by reading .gitignore, so a later rule that
# un-ignores one of these is caught too.
IGNORED_PATHS = (
    "home/.pi/agent/auth.json",
    "home/.pi/agent/web-search.json",
    "home/.pi/agent/web-search-cache/foo",
    "home/.pi/agent/sessions/foo",
    "home/.pi/agent/npm/foo",
    "home/.pi/agent/git/foo",
    "home/.pi/agent/bin/foo",
    "home/.pi/agent/models.json",
    "home/.pi/agent/trust.json",
    "home/.pi/agent/models-store.json",
    "home/.pi/agent/intercom/broker.port.json",
)


def fail(message: str) -> None:
    raise SystemExit(f"doctor: {message}")


def ok(message: str) -> None:
    print(f"ok  {message}")


def prove_source(
    src: str,
    pins: list[dict[str, str]],
    sidecars: list[dict[str, object]],
    quiet: bool = False,
) -> None:
    """Prove the clone. `quiet` proves without narrating, for the preflight.

    Deploy runs this before it writes anything, and doctor runs it again
    afterwards. Printing both times would double every `ok` line for no
    reader's benefit, so the first pass speaks only when it fails.
    """
    say = (lambda _message: None) if quiet else ok
    payload = os.path.join(src, "home")
    agent_src = agent_payload_dir(src)

    for name in REQUIRED_META:
        if not os.path.isfile(os.path.join(src, name)):
            fail(f"missing {os.path.join(src, name)}")
        say(f"meta {name}")

    if os.path.lexists(os.path.join(src, "AGENTS.override.md")):
        fail("AGENTS.override.md was replaced by the root AGENTS.md; delete it")

    for rel in REQUIRED_PAYLOAD:
        if not os.path.isfile(os.path.join(payload, *rel.split("/"))):
            fail(f"missing {os.path.join(payload, rel)}")
        say(f"payload {rel}")

    gitignore = open(os.path.join(src, ".gitignore"), encoding="utf-8").read()
    lines = gitignore.splitlines()
    for line in REQUIRED_IGNORES:
        if line not in lines:
            fail(f".gitignore missing {line}")
    say("gitignore lines")

    for rel in IGNORED_PATHS:
        if not git_ignored(src, rel):
            fail(f"not ignored: {rel}")
    say("check-ignore")

    try:
        json.load(open(os.path.join(agent_src, "settings.json"), encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        fail("settings.json is not JSON")
    say("settings.json json")

    prove_docs(src, pins)
    prove_sidecars_source(src, sidecars)

    if store_owned(os.path.join(agent_src, "AGENTS.md")):
        fail("source payload AGENTS.md is a store symlink")
    say("source payload AGENTS.md not store")


def preflight(
    src: str,
    dest: str,
    pins: list[dict[str, str]],
    sidecars: list[dict[str, object]],
) -> None:
    """Everything that must hold before a landing writes or deletes anything.

    Deploy converges, so it deletes. Proving the clone only afterwards means
    a source tree missing a required payload file has already had the live
    copy pruned by the time doctor says so, and a destination pointing
    inside the clone has already been written to. Both proofs are read-only,
    so running them first costs nothing and removes that window.
    """
    prove_source(src, pins, sidecars, quiet=True)
    prove_dest_location(src, dest)


def prove_dest_location(src: str, dest: str) -> None:
    """The live directory is never this clone. Deploy would land onto source."""
    if not os.environ.get("PI_CODING_AGENT_DIR"):
        return
    clone = os.path.realpath(src)
    resolved = os.path.realpath(dest)
    if resolved == clone or resolved.startswith(clone + os.sep):
        fail(
            f"PI_CODING_AGENT_DIR points inside this clone ({resolved}); "
            "the clone is source, not the live dir"
        )


def prove_copy(source: str, dest_path: str, label: str) -> None:
    if not os.path.isfile(dest_path) or os.path.islink(dest_path):
        fail(f"dest {label} is not a regular file")
    if store_owned(dest_path):
        fail(f"dest {label} is a store symlink")
    if open(source, "rb").read() != open(dest_path, "rb").read():
        fail(f"dest {label} does not match source")
    ok(f"dest {label} copy")


def prove_link(dest_path: str, want: str, label: str) -> None:
    if not os.path.islink(dest_path):
        fail(f"{label} is not a symlink")
    if store_owned(dest_path):
        fail(f"{label} is a store symlink")
    got = os.path.realpath(dest_path)
    if got != os.path.realpath(want):
        fail(f"{label} -> {got}, want {os.path.realpath(want)}")
    ok(f"{label} symlink")


def prove_dest(src: str, dest: str, sidecars: list[dict[str, object]]) -> None:
    agent_src = agent_payload_dir(src)

    prove_copy(
        os.path.join(agent_src, "AGENTS.md"),
        os.path.join(dest, "AGENTS.md"),
        "AGENTS.md",
    )

    if os.path.islink(os.path.join(dest, "prompts")):
        fail("dest prompts/ is a symlink; want a copied directory")
    prove_copy(
        os.path.join(agent_src, "prompts", "review.md"),
        os.path.join(dest, "prompts", "review.md"),
        "prompts/review.md",
    )

    if os.path.islink(os.path.join(dest, "extensions")):
        fail("dest extensions/ is a symlink; want a copied directory")
    prove_copy(
        os.path.join(agent_src, "extensions", "worktree-guard.ts"),
        os.path.join(dest, "extensions", "worktree-guard.ts"),
        "extensions/worktree-guard.ts",
    )

    for name in ("settings.json", "keybindings.json"):
        source = os.path.join(agent_src, name)
        if os.path.isfile(source):
            prove_link(os.path.join(dest, name), source, f"dest {name}")

    # The clone's own rules are machinery. Landing them would give the agent
    # this repository's instructions on every project it opens.
    root_rules = os.path.join(src, "AGENTS.md")
    landed = os.path.join(dest, "AGENTS.md")
    if (
        os.path.isfile(landed)
        and open(root_rules, "rb").read() == open(landed, "rb").read()
    ):
        fail("dest AGENTS.md is the clone-rules file, not the payload")
    ok("dest carries the payload AGENTS.md, not the clone rules")

    auth = os.path.join(dest, "auth.json")
    if os.path.lexists(auth):
        if not os.path.isfile(auth) or os.path.islink(auth):
            fail("dest auth.json is not a regular file")
        mode = stat.S_IMODE(os.stat(auth).st_mode)
        if mode != 0o600:
            fail(f"dest auth.json mode is {mode:o}, want 600")
        ok("dest auth.json mode 600")

    prove_sidecars_landing(src, dest, sidecars)
    prove_manifest(src, dest)


def doctor(
    src: str,
    dest: str,
    pins: list[dict[str, str]],
    sidecars: list[dict[str, object]],
) -> None:
    prove_source(src, pins, sidecars)

    if os.environ.get("DOCTOR_SOURCE_ONLY") == "1":
        return

    prove_dest_location(src, dest)

    if not os.path.isdir(dest):
        print(f"note: dest {dest} does not exist (source-only doctor)")
        return

    prove_dest(src, dest, sidecars)
    note_trees(pins)
