"""Where a path is allowed to be.

Every deletion the engine performs is gated on these four functions. They
decide what counts as inside a landing root, and they are the reason a
swapped directory cannot redirect a prune somewhere else.
"""

from __future__ import annotations

import os
import pathlib

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


class TestRelpathOk:
    @pytest.mark.parametrize(
        "path", [".pi/agent/settings.json", ".pi/lsp-client.json", "a/b/c"]
    )
    def test_accepts_a_plain_relative_path(self, path: str) -> None:
        assert pi_config.relpath_ok(path)

    @pytest.mark.parametrize(
        "path",
        [
            "",
            "/absolute",
            "\\absolute",
            "../escape",
            "a/../b",
            "a/./b",
            "a//b",
            "a/",
        ],
    )
    def test_rejects_anything_that_could_escape(self, path: str) -> None:
        assert not pi_config.relpath_ok(path)


class TestSidecarPaths:
    def test_the_repo_path_is_always_under_the_home_mirror(self) -> None:
        assert (
            pi_config.sidecar_repo_path(".pi/agent/x.json") == "home/.pi/agent/x.json"
        )

    def test_the_source_path_joins_that_onto_the_clone(self) -> None:
        got = pi_config.sidecar_source_path("/src", ".pi/agent/x.json")
        assert got == "/src/home/.pi/agent/x.json"

    def test_an_agent_path_follows_the_agent_dir(self) -> None:
        row: dict[str, object] = {"path": ".pi/agent/x.json"}
        assert pi_config.sidecar_dest_path("/dest", row) == "/dest/x.json"

    def test_a_path_outside_the_agent_dir_lands_under_home(
        self, tmp_home: pathlib.Path
    ) -> None:
        row: dict[str, object] = {"path": ".pi/lsp-client.json"}
        got = pi_config.sidecar_dest_path("/dest", row)
        assert got == str(tmp_home / ".pi" / "lsp-client.json")

    def test_an_agent_path_with_no_dest_yields_nothing(self) -> None:
        """A source-only run has no destination to resolve against."""
        assert pi_config.sidecar_dest_path("", {"path": ".pi/agent/x.json"}) == ""


class TestEntryPath:
    def test_resolves_the_parent_and_keeps_the_leaf(
        self, tmp_path: pathlib.Path
    ) -> None:
        real = tmp_path / "real"
        real.mkdir()
        (real / "file").write_text("x")
        (tmp_path / "via").symlink_to(real)

        # The parent resolves, so both spellings agree.
        assert pi_config.entry_path(str(tmp_path / "via" / "file")) == str(
            real / "file"
        )

    def test_does_not_resolve_the_leaf(self, tmp_path: pathlib.Path) -> None:
        """os.remove acts on the entry, so containment must judge the entry.

        Resolving the leaf would report a deployed symlink's target, which is
        a file inside the clone, and the containment check would then refuse
        to prune every symlink deploy created.
        """
        target = tmp_path / "outside.json"
        target.write_text("{}")
        link = tmp_path / "dest" / "settings.json"
        link.parent.mkdir()
        link.symlink_to(target)

        assert pi_config.entry_path(str(link)) == str(link)


class TestLandingRoots:
    def test_are_the_agent_dir_and_the_pi_dir(self, tmp_home: pathlib.Path) -> None:
        dest = tmp_home / ".pi" / "agent"
        dest.mkdir(parents=True)

        roots = pi_config.landing_roots(str(dest))

        assert roots == [str(dest), str(tmp_home / ".pi")]

    def test_refuse_a_root_that_is_a_symlink(self, tmp_home: pathlib.Path) -> None:
        """A swapped root would redirect every landing and every deletion."""
        elsewhere = tmp_home.parent / "elsewhere"
        elsewhere.mkdir()
        (tmp_home / ".pi").symlink_to(elsewhere)

        with pytest.raises(SystemExit, match="symlink"):
            pi_config.landing_roots(str(tmp_home / ".pi" / "agent"))

    def test_are_not_read_from_any_file(self, tmp_home: pathlib.Path) -> None:
        """Roots are policy derived in code, so a manifest cannot widen them."""
        dest = tmp_home / ".pi" / "agent"
        dest.mkdir(parents=True)
        (dest / ".pi-config-manifest.json").write_text(
            '{"version":1,"roots":["/"],"paths":[]}'
        )

        assert "/" not in pi_config.landing_roots(str(dest))


class TestWithinRoot:
    @pytest.fixture
    def root(self, tmp_path: pathlib.Path) -> pathlib.Path:
        path = tmp_path / "agent"
        path.mkdir()
        return path

    def test_accepts_a_path_under_the_root(self, root: pathlib.Path) -> None:
        assert pi_config.within_root(str(root / "prompts" / "a.md"), str(root))

    def test_rejects_the_root_itself(self, root: pathlib.Path) -> None:
        assert not pi_config.within_root(str(root), str(root))

    def test_rejects_a_lexical_escape(self, root: pathlib.Path) -> None:
        assert not pi_config.within_root(str(root.parent / "elsewhere"), str(root))

    def test_rejects_a_sibling_sharing_a_name_prefix(self, root: pathlib.Path) -> None:
        """`/x/agent-backup` must not count as inside `/x/agent`."""
        sibling = root.parent / (root.name + "-backup")
        sibling.mkdir()
        assert not pi_config.within_root(str(sibling / "a.md"), str(root))

    def test_rejects_an_escape_through_a_symlinked_directory(
        self, root: pathlib.Path, tmp_path: pathlib.Path
    ) -> None:
        """The physical half is what a swapped intermediate directory defeats."""
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "a.md").write_text("x")
        (root / "prompts").symlink_to(outside)

        target = root / "prompts" / "a.md"
        assert os.path.exists(target)
        assert not pi_config.within_root(str(target), str(root))
