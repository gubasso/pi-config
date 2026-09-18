"""Filesystem primitives, including the ones that have to be careful.

`store_owned` is how every recipe recognises a destination Home Manager
still owns. `replace_with_hardlink` is how a sidecar stays one file in two
places for a package that refuses symlinks.
"""

from __future__ import annotations

import os
import pathlib
import stat

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


class TestStoreOwned:
    def test_a_link_into_the_nix_store_is_owned(self, tmp_path: pathlib.Path) -> None:
        link = tmp_path / "AGENTS.md"
        link.symlink_to("/nix/store/does-not-exist-agents-md")
        assert pi_config.store_owned(str(link))

    def test_a_regular_file_is_not(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "AGENTS.md"
        path.write_text("x")
        assert not pi_config.store_owned(str(path))

    def test_a_link_elsewhere_is_not(self, tmp_path: pathlib.Path) -> None:
        target = tmp_path / "real.md"
        target.write_text("x")
        link = tmp_path / "AGENTS.md"
        link.symlink_to(target)
        assert not pi_config.store_owned(str(link))

    def test_a_missing_path_is_not(self, tmp_path: pathlib.Path) -> None:
        assert not pi_config.store_owned(str(tmp_path / "absent"))


class TestBytesRoundTrip:
    def test_write_then_read_returns_the_same_bytes(
        self, tmp_path: pathlib.Path
    ) -> None:
        path = tmp_path / "a" / "b" / "thing.json"
        pi_config.write_bytes(str(path), b'{"a":1}')
        assert pi_config.read_bytes(str(path)) == b'{"a":1}'

    def test_write_creates_the_parent_directories(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "deep" / "deeper" / "thing.json"
        pi_config.write_bytes(str(path), b"{}")
        assert path.parent.is_dir()


class TestSameInode:
    def test_a_hardlinked_pair_shares_an_inode(self, tmp_path: pathlib.Path) -> None:
        left = tmp_path / "left"
        left.write_text("x")
        right = tmp_path / "right"
        os.link(left, right)
        assert pi_config.same_inode(str(left), str(right))

    def test_two_copies_do_not(self, tmp_path: pathlib.Path) -> None:
        left = tmp_path / "left"
        left.write_text("x")
        right = tmp_path / "right"
        right.write_text("x")
        assert not pi_config.same_inode(str(left), str(right))

    def test_a_missing_path_is_not_an_error(self, tmp_path: pathlib.Path) -> None:
        left = tmp_path / "left"
        left.write_text("x")
        assert not pi_config.same_inode(str(left), str(tmp_path / "absent"))


class TestCopyRegular:
    def test_copies_the_bytes_and_sets_a_readable_mode(
        self, tmp_path: pathlib.Path
    ) -> None:
        source = tmp_path / "source"
        source.write_text("payload")
        source.chmod(0o600)
        dest = tmp_path / "dest"

        pi_config.copy_regular(str(source), str(dest))

        assert dest.read_text() == "payload"
        assert stat.S_IMODE(dest.stat().st_mode) == 0o644


class TestReplaceWithHardlink:
    def test_links_when_the_filesystem_allows_it(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "source"
        source.write_text("x")
        dest = tmp_path / "dest" / "thing"

        kind = pi_config.replace_with_hardlink(str(source), str(dest))

        assert kind in ("hardlinked", "copied")
        assert dest.read_text() == "x"
        if kind == "hardlinked":
            assert pi_config.same_inode(str(source), str(dest))

    def test_replaces_an_existing_file(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "source"
        source.write_text("new")
        dest = tmp_path / "dest"
        dest.write_text("old")

        pi_config.replace_with_hardlink(str(source), str(dest))

        assert dest.read_text() == "new"

    def test_refuses_to_replace_a_directory(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "source"
        source.write_text("x")
        dest = tmp_path / "dest"
        dest.mkdir()

        with pytest.raises(SystemExit, match="refusing to replace directory"):
            pi_config.replace_with_hardlink(str(source), str(dest))

    def test_leaves_no_probe_behind(self, tmp_path: pathlib.Path) -> None:
        """The link probe writes into the destination directory."""
        source = tmp_path / "source"
        source.write_text("x")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        pi_config.replace_with_hardlink(str(source), str(dest_dir / "thing"))

        leftovers = [p.name for p in dest_dir.iterdir() if "probe" in p.name]
        assert leftovers == []


class TestProveNofollowRegular:
    def test_accepts_a_regular_file(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "thing.json"
        path.write_text("{}")
        pi_config.prove_nofollow_regular(str(path), "thing.json")

    def test_refuses_a_symlink(self, tmp_path: pathlib.Path) -> None:
        """The package this proof exists for opens with O_NOFOLLOW itself."""
        target = tmp_path / "real.json"
        target.write_text("{}")
        link = tmp_path / "thing.json"
        link.symlink_to(target)

        with pytest.raises(SystemExit, match="without following symlinks"):
            pi_config.prove_nofollow_regular(str(link), "thing.json")

    def test_refuses_a_missing_file(self, tmp_path: pathlib.Path) -> None:
        with pytest.raises(SystemExit):
            pi_config.prove_nofollow_regular(str(tmp_path / "absent"), "absent")


class TestCopyRegularDoesNotWriteThroughASymlink:
    """The destination entry is replaced, never opened through.

    This is a regression the move from bash to Python introduced and a
    review caught. `install -m 0644` unlinks the destination first, so a
    symlinked destination is replaced. `shutil.copyfile` opens it for
    writing, which follows the link and truncates whatever it points at.
    """

    def test_a_symlinked_destination_is_replaced_not_followed(
        self, tmp_path: pathlib.Path
    ) -> None:
        victim = tmp_path / "auth.json"
        victim.write_text('{"token":"secret"}')
        source = tmp_path / "AGENTS.md"
        source.write_text("# payload")
        dest = tmp_path / "dest" / "AGENTS.md"
        dest.parent.mkdir()
        dest.symlink_to(victim)

        pi_config.copy_regular(str(source), str(dest))

        assert victim.read_text() == '{"token":"secret"}'
        assert not dest.is_symlink()
        assert dest.read_text() == "# payload"

    def test_the_mode_lands_on_the_new_file_not_the_target(
        self, tmp_path: pathlib.Path
    ) -> None:
        victim = tmp_path / "auth.json"
        victim.write_text("{}")
        victim.chmod(0o600)
        source = tmp_path / "AGENTS.md"
        source.write_text("x")
        dest = tmp_path / "dest" / "AGENTS.md"
        dest.parent.mkdir()
        dest.symlink_to(victim)

        pi_config.copy_regular(str(source), str(dest))

        assert stat.S_IMODE(victim.stat().st_mode) == 0o600
