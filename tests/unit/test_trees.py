"""Reading what is installed, so convergence knows what to remove.

`installed_npm` reads Pi's own project manifest rather than listing
node_modules, because that tree is one flat npm project holding every
transitive dependency and a directory scan reports dozens of false orphans.
"""

from __future__ import annotations

import json
import pathlib

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


@pytest.fixture
def dest(tmp_home: pathlib.Path) -> pathlib.Path:
    path = tmp_home / ".pi" / "agent"
    path.mkdir(parents=True)
    return path


class TestInstalledNpm:
    def test_reads_the_dependencies_pi_maintains(self, dest: pathlib.Path) -> None:
        npm = dest / "npm"
        npm.mkdir()
        (npm / "package.json").write_text(
            json.dumps({"dependencies": {"pi-thing": "1.0.0"}})
        )

        assert pi_config.installed_npm(str(dest)) == {"pi-thing": "1.0.0"}

    def test_keeps_a_scope_on_the_key(self, dest: pathlib.Path) -> None:
        npm = dest / "npm"
        npm.mkdir()
        (npm / "package.json").write_text(
            json.dumps({"dependencies": {"@scope/pi-thing": "1.0.0"}})
        )

        assert "@scope/pi-thing" in pi_config.installed_npm(str(dest))

    def test_does_not_list_node_modules(self, dest: pathlib.Path) -> None:
        """Every transitive dependency lives there and none of them is a pin."""
        npm = dest / "npm"
        (npm / "node_modules" / "left-pad").mkdir(parents=True)
        (npm / "package.json").write_text(json.dumps({"dependencies": {}}))

        assert pi_config.installed_npm(str(dest)) == {}

    @pytest.mark.parametrize(
        "body", ["{not json", json.dumps({}), json.dumps({"dependencies": []})]
    )
    def test_an_unreadable_manifest_reports_nothing(
        self, dest: pathlib.Path, body: str
    ) -> None:
        """Reporting a guess here would orphan a package that is installed."""
        npm = dest / "npm"
        npm.mkdir()
        (npm / "package.json").write_text(body)

        assert pi_config.installed_npm(str(dest)) == {}

    def test_a_missing_manifest_reports_nothing(self, dest: pathlib.Path) -> None:
        assert pi_config.installed_npm(str(dest)) == {}


class TestInstalledGit:
    def test_finds_a_clone_and_keys_it_by_its_pin(self, dest: pathlib.Path) -> None:
        clone = dest / "git" / "github.com" / "user" / "repo"
        (clone / ".git").mkdir(parents=True)

        got = pi_config.installed_git(str(dest))
        assert got == {"git:github.com/user/repo": str(clone)}

    def test_stops_descending_at_the_clone(self, dest: pathlib.Path) -> None:
        """A nested checkout inside a package is that package's business."""
        clone = dest / "git" / "github.com" / "user" / "repo"
        (clone / ".git").mkdir(parents=True)
        (clone / "vendor" / "other" / ".git").mkdir(parents=True)

        assert list(pi_config.installed_git(str(dest))) == ["git:github.com/user/repo"]

    def test_a_directory_with_no_git_is_not_a_clone(self, dest: pathlib.Path) -> None:
        (dest / "git" / "github.com" / "user" / "repo").mkdir(parents=True)
        assert pi_config.installed_git(str(dest)) == {}

    def test_a_missing_tree_reports_nothing(self, dest: pathlib.Path) -> None:
        assert pi_config.installed_git(str(dest)) == {}


class TestNoteTrees:
    def test_says_nothing_is_wrong_when_every_tree_is_present(
        self, dest: pathlib.Path, capsys: pytest.CaptureFixture
    ) -> None:
        tree = dest / "npm" / "node_modules" / "pi-thing"
        tree.mkdir(parents=True)
        pins = [
            {
                "pin": "npm:pi-thing",
                "name": "pi-thing",
                "kind": "npm",
                "tree": str(tree),
                "frozen": "",
            }
        ]

        pi_config.note_trees(pins)
        assert "ok  package trees" in capsys.readouterr().out

    def test_a_missing_tree_is_a_note_rather_than_a_failure(
        self, dest: pathlib.Path, capsys: pytest.CaptureFixture
    ) -> None:
        """An uninstalled package is a state to fix, not a broken contract."""
        pins = [
            {
                "pin": "npm:pi-thing",
                "name": "pi-thing",
                "kind": "npm",
                "tree": str(dest / "npm" / "node_modules" / "pi-thing"),
                "frozen": "",
            }
        ]

        pi_config.note_trees(pins)
        assert "tree missing" in capsys.readouterr().err
