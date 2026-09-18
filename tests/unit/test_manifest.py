"""The deploy manifest: what it records, and what it refuses to believe.

The manifest is the only thing that decides which paths prune may consider.
It is recorded as a side effect of landing and never recomputed, because a
parallel enumeration would have to repeat every skip rule and a divergence
there deletes a file deploy never landed.

Reading it is deliberately forgiving and never guesses: an unreadable or
unfamiliar manifest means no prune this run, not a prune of everything.
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


@pytest.fixture
def dest(tmp_home: pathlib.Path) -> pathlib.Path:
    path = tmp_home / ".pi" / "agent"
    path.mkdir(parents=True)
    return path


class TestTheRunRecord:
    """What this deploy landed, held in the process that landed it.

    This was a tab-delimited temp file, because bash did half the landing and
    Python did the other half. One process does all of it now, so the record
    is a dictionary and the file is gone.
    """

    @pytest.fixture(autouse=True)
    def fresh(self) -> None:
        pi_config.reset_landed()

    def test_records_what_landed_and_how(self) -> None:
        pi_config.record("copy", "/dest/AGENTS.md")
        pi_config.record("symlink", "/dest/settings.json")

        assert pi_config.landed() == [
            ("/dest/AGENTS.md", "copy"),
            ("/dest/settings.json", "symlink"),
        ]

    def test_stores_an_absolute_path(self, tmp_path: pathlib.Path) -> None:
        """Prune compares against the manifest, which is always absolute."""
        os.chdir(tmp_path)
        pi_config.record("copy", "relative.md")

        assert pi_config.landed() == [(str(tmp_path / "relative.md"), "copy")]

    def test_the_last_how_for_a_path_wins(self) -> None:
        pi_config.record("dir", "/dest/a")
        pi_config.record("copy", "/dest/a")

        assert pi_config.landed() == [("/dest/a", "copy")]

    def test_reset_starts_a_new_deploy(self) -> None:
        pi_config.record("copy", "/dest/a")
        pi_config.reset_landed()

        assert pi_config.landed() == []

    def test_an_empty_record_is_fatal(self) -> None:
        """Landing nothing would read as every previous path being stale."""
        with pytest.raises(SystemExit, match="landed nothing"):
            pi_config.read_run_manifest()

    def test_a_non_empty_record_is_what_converge_reads(self) -> None:
        pi_config.record("copy", "/dest/AGENTS.md")
        assert pi_config.read_run_manifest() == [("/dest/AGENTS.md", "copy")]


class TestWriteAndReadManifest:
    def test_a_round_trip_keeps_every_path_and_how(self, dest: pathlib.Path) -> None:
        landed = [
            (str(dest / "AGENTS.md"), "copy"),
            (str(dest / "settings.json"), "symlink"),
            (str(dest / "prompts"), "dir"),
        ]
        pi_config.write_manifest("/src", str(dest), landed)

        got = pi_config.read_manifest(str(dest))
        assert [(row["path"], row["how"]) for row in got] == landed

    def test_records_the_source_it_was_written_from(self, dest: pathlib.Path) -> None:
        pi_config.write_manifest("/src", str(dest), [])
        doc = json.loads((dest / pi_config.MANIFEST_NAME).read_text())

        assert doc["source"] == "/src"
        assert doc["version"] == pi_config.MANIFEST_VERSION
        assert doc["deployedAt"].endswith("Z")

    def test_writing_replaces_the_entry_rather_than_the_target(
        self, dest: pathlib.Path, tmp_path: pathlib.Path
    ) -> None:
        """Opening for write would follow a planted link and truncate it."""
        victim = tmp_path / "victim.txt"
        victim.write_text("important")
        (dest / pi_config.MANIFEST_NAME).symlink_to(victim)

        with pytest.raises(SystemExit, match="symlink"):
            pi_config.write_manifest("/src", str(dest), [])

        assert victim.read_text() == "important"

    def test_a_failed_write_leaves_no_temporary_file(self, dest: pathlib.Path) -> None:
        pi_config.write_manifest("/src", str(dest), [])
        leftovers = [p for p in os.listdir(dest) if p.endswith(".tmp")]
        assert leftovers == []


class TestReadManifestRefusesToGuess:
    """Every unreadable shape yields no prune, never a prune of everything."""

    def test_a_missing_manifest_reads_as_empty(self, dest: pathlib.Path) -> None:
        assert pi_config.read_manifest(str(dest)) == []

    def test_broken_json_reads_as_empty(self, dest: pathlib.Path) -> None:
        (dest / pi_config.MANIFEST_NAME).write_text("{not json")
        assert pi_config.read_manifest(str(dest)) == []

    def test_a_future_version_reads_as_empty(self, dest: pathlib.Path) -> None:
        (dest / pi_config.MANIFEST_NAME).write_text(
            json.dumps(
                {"version": pi_config.MANIFEST_VERSION + 1, "paths": [{"path": "/x"}]}
            )
        )
        assert pi_config.read_manifest(str(dest)) == []

    def test_a_missing_paths_array_reads_as_empty(self, dest: pathlib.Path) -> None:
        (dest / pi_config.MANIFEST_NAME).write_text(
            json.dumps({"version": pi_config.MANIFEST_VERSION})
        )
        assert pi_config.read_manifest(str(dest)) == []

    def test_a_row_with_no_path_is_dropped(self, dest: pathlib.Path) -> None:
        (dest / pi_config.MANIFEST_NAME).write_text(
            json.dumps(
                {
                    "version": pi_config.MANIFEST_VERSION,
                    "paths": [{"how": "copy"}, "nonsense", {"path": "/keep"}],
                }
            )
        )
        assert pi_config.read_manifest(str(dest)) == [{"path": "/keep", "how": "copy"}]

    def test_a_row_with_no_how_defaults_to_copy(self, dest: pathlib.Path) -> None:
        (dest / pi_config.MANIFEST_NAME).write_text(
            json.dumps(
                {"version": pi_config.MANIFEST_VERSION, "paths": [{"path": "/x"}]}
            )
        )
        assert pi_config.read_manifest(str(dest)) == [{"path": "/x", "how": "copy"}]
