"""What `just status` reports.

A report, not a gate. It never fails a run, so the only thing to get wrong
is telling the operator a package is landed when it is not.
"""

from __future__ import annotations

import os
import pathlib

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


def pin(**overrides: object) -> dict[str, str]:
    base = {
        "pin": "npm:pi-thing",
        "name": "pi-thing",
        "kind": "npm",
        "tree": "",
        "frozen": "",
    }
    base.update(overrides)  # type: ignore[arg-type]
    return base  # type: ignore[return-value]


@pytest.fixture
def clone(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "clone"
    (root / "home" / ".pi" / "agent").mkdir(parents=True)
    return root


@pytest.fixture
def dest(tmp_home: pathlib.Path) -> pathlib.Path:
    path = tmp_home / ".pi" / "agent"
    path.mkdir(parents=True)
    return path


class TestPins:
    def test_says_none_when_nothing_is_pinned(
        self, clone: pathlib.Path, dest: pathlib.Path, capsys: pytest.CaptureFixture
    ) -> None:
        pi_config.print_status(str(clone), str(dest), [], [])
        out = capsys.readouterr().out
        assert "packages none" in out
        assert f"source {clone}" in out

    def test_reports_missing_docs_and_a_missing_tree(
        self, clone: pathlib.Path, dest: pathlib.Path, capsys: pytest.CaptureFixture
    ) -> None:
        pi_config.print_status(str(clone), str(dest), [pin()], [])
        out = capsys.readouterr().out
        assert "docs no" in out
        assert "tree no" in out

    def test_reports_a_complete_docs_set(
        self, clone: pathlib.Path, dest: pathlib.Path, capsys: pytest.CaptureFixture
    ) -> None:
        docs = clone / "docs" / "plugins" / "pi-thing"
        docs.mkdir(parents=True)
        for name in ("README.md", "SPEC.md", "sidecars.json"):
            (docs / name).write_text("")

        pi_config.print_status(str(clone), str(dest), [pin()], [])
        assert "docs yes" in capsys.readouterr().out

    def test_reports_an_installed_tree(
        self, clone: pathlib.Path, dest: pathlib.Path, capsys: pytest.CaptureFixture
    ) -> None:
        tree = dest / "npm" / "node_modules" / "pi-thing"
        tree.mkdir(parents=True)

        pi_config.print_status(str(clone), str(dest), [pin(tree=str(tree))], [])
        assert "tree yes" in capsys.readouterr().out

    def test_names_a_freeze_and_its_ref(
        self, clone: pathlib.Path, dest: pathlib.Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A freeze is a departure from the rule, so the report says so."""
        pi_config.print_status(str(clone), str(dest), [pin(frozen="1.2.3")], [])
        out = capsys.readouterr().out
        assert "frozen 1.2.3" in out
        assert "unversioned" not in out

    def test_calls_an_unfrozen_pin_unversioned(
        self, clone: pathlib.Path, dest: pathlib.Path, capsys: pytest.CaptureFixture
    ) -> None:
        pi_config.print_status(str(clone), str(dest), [pin()], [])
        assert "unversioned" in capsys.readouterr().out


class TestSidecars:
    def row(self, klass: str) -> dict[str, object]:
        return {"path": ".pi/agent/thing.json", "class": klass}

    def test_reports_an_absent_destination(
        self, clone: pathlib.Path, dest: pathlib.Path, capsys: pytest.CaptureFixture
    ) -> None:
        pi_config.print_status(str(clone), str(dest), [pin()], [self.row("copy")])
        assert "dest no" in capsys.readouterr().out

    def test_reports_a_symlink(
        self, clone: pathlib.Path, dest: pathlib.Path, capsys: pytest.CaptureFixture
    ) -> None:
        source = clone / "home" / ".pi" / "agent" / "thing.json"
        source.write_text("{}")
        (dest / "thing.json").symlink_to(source)

        pi_config.print_status(str(clone), str(dest), [pin()], [self.row("symlink")])
        assert "dest symlink" in capsys.readouterr().out

    def test_distinguishes_a_hardlink_from_a_plain_copy(
        self, clone: pathlib.Path, dest: pathlib.Path, capsys: pytest.CaptureFixture
    ) -> None:
        """The difference is the whole point of followsSymlinks: false."""
        source = clone / "home" / ".pi" / "agent" / "thing.json"
        source.write_text("{}")
        os.link(source, dest / "thing.json")

        pi_config.print_status(str(clone), str(dest), [pin()], [self.row("copy")])
        assert "dest hardlink" in capsys.readouterr().out

        (dest / "thing.json").unlink()
        (dest / "thing.json").write_text("{}")
        pi_config.print_status(str(clone), str(dest), [pin()], [self.row("copy")])
        assert "dest file" in capsys.readouterr().out
