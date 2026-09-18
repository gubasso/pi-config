"""The sidecars.json validator.

This is the only thing standing between a wrong `docs/plugins/<name>/` entry
and a wrong landing. A sensitive file classified `symlink` would put a token
into git. A runtime-written file classified `copy` would have deploy fight the
runtime on every write. Every rejection below is one of those.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]

PLUGIN = "pi-thing"
PIN = "npm:pi-thing"


@pytest.fixture
def write_sidecars(tmp_path: pathlib.Path):
    """Write a docs/plugins/pi-thing/sidecars.json and return the clone root."""

    def write(document: object) -> str:
        docs = tmp_path / "docs" / "plugins" / PLUGIN
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "sidecars.json").write_text(json.dumps(document))
        return str(tmp_path)

    return write


def row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"path": ".pi/agent/thing.json", "class": "copy"}
    base.update(overrides)
    return base


def load(src: str) -> list[dict[str, object]]:
    return pi_config.load_plugin_sidecars(src, PLUGIN, PIN)


class TestAccepts:
    def test_an_empty_sidecars_array(self, write_sidecars) -> None:
        """A package that reads no config file still declares that.

        The empty array is the difference between checked and unchecked.
        """
        assert load(write_sidecars({"sidecars": []})) == []

    def test_a_copy_row_and_fills_in_the_defaults(self, write_sidecars) -> None:
        got = load(write_sidecars({"sidecars": [row()]}))

        assert got == [
            {
                "plugin": PLUGIN,
                "pin": PIN,
                "path": ".pi/agent/thing.json",
                "class": "copy",
                "sensitive": False,
                "runtimeWrites": False,
                "required": True,
                "followsSymlinks": True,
            }
        ]

    def test_a_live_only_row_is_never_required(self, write_sidecars) -> None:
        """This repository does not track it, so it cannot be required here."""
        got = load(
            write_sidecars(
                {"sidecars": [row(**{"class": "live-only", "sensitive": True})]}
            )
        )
        assert got[0]["required"] is False

    def test_a_runtime_written_row_as_a_symlink(self, write_sidecars) -> None:
        got = load(
            write_sidecars(
                {"sidecars": [row(**{"class": "symlink", "runtimeWrites": True})]}
            )
        )
        assert got[0]["class"] == "symlink"

    def test_a_runtime_written_copy_when_the_package_refuses_symlinks(
        self, write_sidecars
    ) -> None:
        """The hardlink and 3-way sync path, for a package using O_NOFOLLOW."""
        got = load(
            write_sidecars(
                {"sidecars": [row(**{"runtimeWrites": True, "followsSymlinks": False})]}
            )
        )
        assert got[0]["followsSymlinks"] is False

    def test_a_path_under_pi_but_outside_the_agent_dir(self, write_sidecars) -> None:
        got = load(write_sidecars({"sidecars": [row(path=".pi/lsp-client.json")]}))
        assert got[0]["path"] == ".pi/lsp-client.json"


class TestRefuses:
    def test_a_missing_file(self, tmp_path: pathlib.Path) -> None:
        """A pin without a classified sidecars.json is unfinished."""
        with pytest.raises(SystemExit, match="missing"):
            load(str(tmp_path))

    def test_broken_json(self, tmp_path: pathlib.Path) -> None:
        docs = tmp_path / "docs" / "plugins" / PLUGIN
        docs.mkdir(parents=True)
        (docs / "sidecars.json").write_text("{not json")

        with pytest.raises(SystemExit, match="not JSON"):
            load(str(tmp_path))

    @pytest.mark.parametrize(
        "document", [[], "text", {}, {"sidecars": {}}, {"sidecars": "none"}]
    )
    def test_anything_but_an_object_with_a_sidecars_array(
        self, write_sidecars, document: object
    ) -> None:
        with pytest.raises(SystemExit, match="sidecars array"):
            load(write_sidecars(document))

    def test_a_row_that_is_not_an_object(self, write_sidecars) -> None:
        with pytest.raises(SystemExit, match="must be an object"):
            load(write_sidecars({"sidecars": ["thing.json"]}))

    def test_an_unknown_key(self, write_sidecars) -> None:
        """A typo in a key would otherwise pass as a silent default."""
        with pytest.raises(SystemExit, match="unknown keys"):
            load(write_sidecars({"sidecars": [row(runtimeWrite=True)]}))

    @pytest.mark.parametrize(
        "path",
        ["", "/abs/thing.json", "../escape.json", ".pi/../../escape", 7, None],
    )
    def test_a_path_that_is_not_a_safe_relative_path(
        self, write_sidecars, path: object
    ) -> None:
        with pytest.raises(SystemExit, match="relative path"):
            load(write_sidecars({"sidecars": [row(path=path)]}))

    @pytest.mark.parametrize("path", ["config/thing.json", ".config/pi/thing.json"])
    def test_a_path_outside_the_landing_roots(self, write_sidecars, path: str) -> None:
        """Deploy holds delete authority only under the agent dir and ~/.pi."""
        with pytest.raises(SystemExit, match="must start with"):
            load(write_sidecars({"sidecars": [row(path=path)]}))

    @pytest.mark.parametrize("klass", ["link", "hardlink", "", None, "COPY"])
    def test_a_class_outside_the_three(self, write_sidecars, klass: object) -> None:
        with pytest.raises(SystemExit, match="class must be one of"):
            load(write_sidecars({"sidecars": [row(**{"class": klass})]}))

    def test_a_duplicate_path(self, write_sidecars) -> None:
        with pytest.raises(SystemExit, match="duplicate"):
            load(write_sidecars({"sidecars": [row(), row()]}))

    @pytest.mark.parametrize("key", ["sensitive", "runtimeWrites"])
    def test_a_non_boolean_flag(self, write_sidecars, key: str) -> None:
        with pytest.raises(SystemExit, match="must be booleans"):
            load(write_sidecars({"sidecars": [row(**{key: "yes"})]}))

    def test_a_non_boolean_required(self, write_sidecars) -> None:
        with pytest.raises(SystemExit, match="required must be a boolean"):
            load(write_sidecars({"sidecars": [row(required="yes")]}))

    def test_a_non_boolean_follows_symlinks(self, write_sidecars) -> None:
        with pytest.raises(SystemExit, match="followsSymlinks must be a boolean"):
            load(write_sidecars({"sidecars": [row(followsSymlinks="no")]}))

    @pytest.mark.parametrize("klass", ["copy", "symlink"])
    def test_a_sensitive_file_that_is_not_live_only(
        self, write_sidecars, klass: str
    ) -> None:
        """This is the rule that keeps a token out of git."""
        with pytest.raises(SystemExit, match="must be class live-only"):
            load(
                write_sidecars(
                    {"sidecars": [row(**{"class": klass, "sensitive": True})]}
                )
            )

    @pytest.mark.parametrize("klass", ["symlink", "live-only"])
    def test_follows_symlinks_false_outside_copy(
        self, write_sidecars, klass: str
    ) -> None:
        with pytest.raises(SystemExit, match="requires class copy"):
            load(
                write_sidecars(
                    {"sidecars": [row(**{"class": klass, "followsSymlinks": False})]}
                )
            )

    def test_a_runtime_written_copy_that_does_follow_symlinks(
        self, write_sidecars
    ) -> None:
        """Copying it on every deploy would fight the runtime forever."""
        with pytest.raises(SystemExit, match="must be class symlink"):
            load(write_sidecars({"sidecars": [row(runtimeWrites=True)]}))
