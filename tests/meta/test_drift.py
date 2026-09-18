"""Rules this tree states more than once, kept saying the same thing.

Each case below is a rule written in two or three files because two or three
tools need it. Every one of them was prose before this, and prose does not
fail a build. SPEC.md even says "Add a new runtime-written file to both
lists at once", which is a rule about a rule and nothing enforced it.
"""

from __future__ import annotations

import fnmatch
import json
import pathlib
import re
import subprocess

import pytest
import yaml

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


def tracked(repo_root: pathlib.Path, prefix: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", prefix],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


class TestRuntimeOwnedSet:
    """The names Pi writes, declared in prune.py, .gitignore, and SPEC.md."""

    def test_gitignore_covers_every_runtime_path_doctor_requires(
        self, repo_root: pathlib.Path
    ) -> None:
        lines = (repo_root / ".gitignore").read_text().splitlines()
        missing = [line for line in pi_config.REQUIRED_IGNORES if line not in lines]
        assert missing == []

    def test_every_required_ignore_names_something_the_veto_knows(
        self, repo_root: pathlib.Path
    ) -> None:
        """A path worth gitignoring is a path prune must refuse to delete."""
        known = pi_config.RUNTIME_OWNED_NAMES | pi_config.RUNTIME_OWNED_DIRS
        unknown = []
        for line in pi_config.REQUIRED_IGNORES:
            leaf = line.rstrip("/").rsplit("/", 1)[-1]
            if leaf not in known:
                unknown.append(line)
        assert unknown == []

    def test_the_spec_lists_what_the_veto_refuses(
        self, repo_root: pathlib.Path
    ) -> None:
        """SPEC.md §5 names what Pi creates in the live directory.

        A name in that block and not in the veto is a file prune would
        delete while the specification says Pi owns it.
        """
        spec = (repo_root / "SPEC.md").read_text()
        block = re.search(
            r"Pi will still create these in the \*\*live\*\* agent directory.*?"
            r"```text\n(.*?)```",
            spec,
            re.S,
        )
        assert block is not None, "SPEC.md no longer lists what Pi creates"

        known = pi_config.RUNTIME_OWNED_NAMES | pi_config.RUNTIME_OWNED_DIRS
        missing = []
        for entry in block.group(1).split():
            name = entry.rstrip("/").rsplit("/", 1)[-1]
            if "*" in name:
                # A glob stands for a family the veto lists by name, such as
                # `broker.*` for the sockets and locks pi-intercom writes.
                pattern = re.compile(fnmatch.translate(name))
                if any(pattern.match(candidate) for candidate in known):
                    continue
            elif name in known:
                continue
            missing.append(entry)
        assert missing == [], f"SPEC.md names these and the veto does not: {missing}"


class TestFormatterAndFixerAgree:
    """dprint and the whitespace fixers must skip the same runtime files.

    Pi rewrites these itself. A formatter fights the runtime on every write,
    and it also replaces a file atomically, which breaks the hardlink a
    `followsSymlinks: false` sidecar depends on.
    """

    def dprint_excludes(self, repo_root: pathlib.Path) -> set[str]:
        config = json.loads((repo_root / "dprint.json").read_text())
        return {e for e in config["excludes"] if e.startswith("home/")}

    def anchor_excludes(self, repo_root: pathlib.Path) -> set[str]:
        config = yaml.safe_load((repo_root / ".pre-commit-config.yaml").read_text())
        patterns = {
            hook["exclude"]
            for repo in config["repos"]
            for hook in repo["hooks"]
            if "exclude" in hook and hook["exclude"].startswith("^home/")
        }
        assert len(patterns) == 1, "the runtime_owned anchor is no longer shared"
        pattern = patterns.pop()
        inner = re.search(r"\((.*)\)\$$", pattern)
        assert inner is not None
        prefix = pattern[len("^") : pattern.index("(")]
        return {prefix + alt for alt in inner.group(1).split("|")}

    def test_both_lists_name_the_same_files(self, repo_root: pathlib.Path) -> None:
        dprint = {e.replace(".", r"\.") for e in self.dprint_excludes(repo_root)}
        anchor = self.anchor_excludes(repo_root)

        # dprint spells a directory wildcard `**`, the anchor spells it `.*`.
        normalise = lambda s: s.replace("**", "*").replace(".*", "*")  # noqa: E731
        assert {normalise(e) for e in dprint} == {normalise(e) for e in anchor}


class TestDevshellCheckMatchesTheFlake:
    def test_every_tool_the_loop_probes_is_in_the_flake(
        self, repo_root: pathlib.Path
    ) -> None:
        """`just devshell-check` is the executable form of the flake's claim.

        A tool in the loop and not in the flake makes the recipe fail on a
        clean machine, which is exactly the report it exists to give. A tool
        in the flake and not in the loop is never proved present.
        """
        justfile = (repo_root / "justfile").read_text()
        loop = re.search(r"for t in (.*?); do", justfile, re.S)
        assert loop is not None
        probed = set(loop.group(1).replace("\\\n", " ").split())

        flake = (repo_root / "flake.nix").read_text()

        # A package's attribute name is not always its command name.
        COMMANDS = {
            "node": "nodejs",
            "pytest": "python3.withPackages",
            "tsc": "typescript",
            "pyright-langserver": "pyright",
            "vscode-json-language-server": "vscode-langservers-extracted",
            "vitest": "importNpmLock",
        }
        missing = [tool for tool in probed if COMMANDS.get(tool, tool) not in flake]
        assert missing == [], f"probed but not in flake.nix: {sorted(missing)}"


class TestPayloadIsDeployable:
    def test_every_tracked_payload_file_is_landed_somehow(
        self, repo_root: pathlib.Path
    ) -> None:
        """Nothing is tracked under home/ and silently never deployed.

        Deploy lands the named files, the named directories, and every
        classified sidecar. A tracked file outside all three reaches no
        machine, and nothing would say so.
        """
        agent = "home/.pi/agent/"
        landed_names = set(pi_config.PAYLOAD_FILES) | set(pi_config.LINKED_FILES)

        sidecar_paths = set()
        for docs in sorted((repo_root / "docs" / "plugins").iterdir()):
            manifest = docs / "sidecars.json"
            if not manifest.is_file():
                continue
            for row in json.loads(manifest.read_text())["sidecars"]:
                sidecar_paths.add("home/" + row["path"])

        stranded = []
        for path in tracked(repo_root, "home"):
            if path in sidecar_paths:
                continue
            if not path.startswith(agent):
                continue
            rel = path[len(agent) :]
            if rel in landed_names:
                continue
            if rel.split("/")[0] in pi_config.PAYLOAD_DIRS:
                continue
            stranded.append(path)

        assert stranded == [], f"tracked but never deployed: {stranded}"

    def test_nothing_but_regular_files_sits_under_extensions(
        self, repo_root: pathlib.Path
    ) -> None:
        """Deploy copies one level, so a subdirectory here lands nowhere.

        Until deploy learns to recurse, an extension is one file.
        """
        extensions = repo_root / "home" / ".pi" / "agent" / "extensions"
        nested = [
            str(entry.relative_to(repo_root))
            for entry in extensions.iterdir()
            if entry.is_dir()
            and str(entry.relative_to(repo_root)) + "/"
            not in {p.rsplit("/", 1)[0] + "/" for p in tracked(repo_root, "home")}
        ]
        # A directory is allowed only when a sidecar declares a file inside it.
        assert nested == [], f"would be dropped at deploy: {nested}"
