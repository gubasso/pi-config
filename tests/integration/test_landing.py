"""Landing a sidecar: copy, symlink, and the hardlink a package can demand.

Real files under tmp_path, no host state. The three classes land three
different ways, and the third one exists because a package that opens its
config with O_NOFOLLOW and rewrites it by atomic rename cannot be given a
symlink and cannot be given a plain copy either.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


@pytest.fixture
def clone(tmp_path: pathlib.Path, tmp_home: pathlib.Path) -> pathlib.Path:
    """A minimal source tree with a git history, as land_atomic_sot needs."""
    root = tmp_path / "clone"
    (root / "home" / ".pi" / "agent").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


@pytest.fixture
def dest(tmp_home: pathlib.Path) -> pathlib.Path:
    path = tmp_home / ".pi" / "agent"
    path.mkdir(parents=True)
    return path


@pytest.fixture
def recording(tmp_home: pathlib.Path) -> None:
    """Start each test with an empty landing record.

    Landing notes every path it creates, and the record lives in the process
    rather than in a file, so a test that does not clear it inherits whatever
    the previous one landed.
    """
    pi_config.reset_landed()


def commit(clone: pathlib.Path, message: str = "x") -> None:
    subprocess.run(["git", "add", "-A"], cwd=clone, check=True)
    subprocess.run(["git", "commit", "-qm", message], cwd=clone, check=True)


def sidecar(clone: pathlib.Path, rel: str, body: str) -> pathlib.Path:
    path = pathlib.Path(pi_config.sidecar_source_path(str(clone), rel))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


def row(rel: str, klass: str, **extra: object) -> dict[str, object]:
    base: dict[str, object] = {
        "plugin": "pi-thing",
        "pin": "npm:pi-thing",
        "path": rel,
        "class": klass,
        "sensitive": False,
        "runtimeWrites": False,
        "required": True,
        "followsSymlinks": True,
    }
    base.update(extra)
    return base


@pytest.mark.usefixtures("recording")
class TestLandSidecars:
    def test_a_copy_lands_as_a_regular_file(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        sidecar(clone, ".pi/agent/thing.json", '{"a":1}')

        pi_config.land_sidecars(
            str(clone), str(dest), [row(".pi/agent/thing.json", "copy")]
        )

        landed = dest / "thing.json"
        assert landed.read_text() == '{"a":1}'
        assert not landed.is_symlink()

    def test_a_symlink_lands_pointing_at_the_source(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        source = sidecar(clone, ".pi/agent/thing.json", "{}")

        pi_config.land_sidecars(
            str(clone), str(dest), [row(".pi/agent/thing.json", "symlink")]
        )

        landed = dest / "thing.json"
        assert landed.is_symlink()
        assert os.path.realpath(landed) == os.path.realpath(source)

    def test_a_live_only_row_is_never_touched(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        """It can hold a token, so this repository never creates or reads it."""
        pi_config.land_sidecars(
            str(clone),
            str(dest),
            [row(".pi/agent/secret.json", "live-only", sensitive=True)],
        )
        assert not (dest / "secret.json").exists()

    def test_a_missing_required_source_fails_the_run(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        with pytest.raises(SystemExit, match="missing source sidecar"):
            pi_config.land_sidecars(
                str(clone), str(dest), [row(".pi/agent/absent.json", "copy")]
            )

    def test_a_missing_optional_source_is_skipped(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        pi_config.land_sidecars(
            str(clone),
            str(dest),
            [row(".pi/agent/absent.json", "copy", required=False)],
        )
        assert not (dest / "absent.json").exists()

    def test_a_nested_path_creates_its_directory(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        sidecar(clone, ".pi/agent/intercom/config.json", "{}")

        pi_config.land_sidecars(
            str(clone), str(dest), [row(".pi/agent/intercom/config.json", "copy")]
        )
        assert (dest / "intercom" / "config.json").read_text() == "{}"

    def test_a_store_symlink_at_the_destination_fails_the_run(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        sidecar(clone, ".pi/agent/thing.json", "{}")
        (dest / "thing.json").symlink_to("/nix/store/does-not-exist-thing")

        with pytest.raises(SystemExit, match="Home Manager"):
            pi_config.land_sidecars(
                str(clone), str(dest), [row(".pi/agent/thing.json", "copy")]
            )

    def test_landing_is_recorded_for_the_manifest(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        sidecar(clone, ".pi/agent/thing.json", "{}")

        pi_config.land_sidecars(
            str(clone), str(dest), [row(".pi/agent/thing.json", "copy")]
        )

        assert (str(dest / "thing.json"), "copy") in pi_config.landed()


@pytest.mark.usefixtures("recording")
class TestLandAtomicSot:
    """followsSymlinks: false. A hardlink, kept in step by a 3-way merge.

    The two paths share an inode, so the package's own writes are visible in
    the clone. An atomic rename breaks that, which is why every deploy
    re-establishes it and reconciles whatever happened in between.
    """

    def land(self, clone: pathlib.Path, dest: pathlib.Path) -> None:
        pi_config.land_sidecars(
            str(clone),
            str(dest),
            [row(".pi/agent/thing.json", "copy", followsSymlinks=False)],
        )

    def test_a_first_landing_shares_an_inode_with_the_source(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        source = sidecar(clone, ".pi/agent/thing.json", '{"a":1}')
        commit(clone)

        self.land(clone, dest)

        assert pi_config.same_inode(str(source), str(dest / "thing.json"))

    def test_an_unchanged_destination_relinks(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        source = sidecar(clone, ".pi/agent/thing.json", '{"a":1}')
        commit(clone)
        self.land(clone, dest)

        # An atomic rename by the package breaks the link without changing
        # the bytes.
        landed = dest / "thing.json"
        replacement = dest / "thing.json.new"
        replacement.write_text('{"a":1}')
        replacement.replace(landed)
        assert not pi_config.same_inode(str(source), str(landed))

        self.land(clone, dest)
        assert pi_config.same_inode(str(source), str(landed))

    def test_a_changed_source_wins_over_an_untouched_destination(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        sidecar(clone, ".pi/agent/thing.json", '{"a":1}')
        commit(clone)
        self.land(clone, dest)

        sidecar(clone, ".pi/agent/thing.json", '{"a":2}')

        self.land(clone, dest)
        assert (dest / "thing.json").read_text() == '{"a":2}'

    def test_a_changed_destination_is_imported_into_the_source(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        """The runtime wrote it, so the clone takes the new bytes."""
        source = sidecar(clone, ".pi/agent/thing.json", '{"a":1}')
        commit(clone)
        self.land(clone, dest)

        landed = dest / "thing.json"
        replacement = dest / "thing.json.new"
        replacement.write_text('{"a":"written by the runtime"}')
        replacement.replace(landed)

        self.land(clone, dest)
        assert source.read_text() == '{"a":"written by the runtime"}'
        assert pi_config.same_inode(str(source), str(landed))

    def test_both_sides_changed_is_a_conflict_the_operator_resolves(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        sidecar(clone, ".pi/agent/thing.json", '{"a":1}')
        commit(clone)
        self.land(clone, dest)

        landed = dest / "thing.json"
        replacement = dest / "thing.json.new"
        replacement.write_text('{"a":"dest"}')
        replacement.replace(landed)
        sidecar(clone, ".pi/agent/thing.json", '{"a":"source"}')

        with pytest.raises(SystemExit, match="conflict"):
            self.land(clone, dest)

    def test_a_file_absent_from_head_names_that_in_the_conflict(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        """With no base there is nothing to merge against, and it says so."""
        sidecar(clone, ".pi/agent/thing.json", '{"a":"source"}')
        (dest / "thing.json").write_text('{"a":"dest"}')

        with pytest.raises(SystemExit, match="not in HEAD"):
            self.land(clone, dest)


@pytest.mark.usefixtures("recording")
class TestLandingStaysInsideTheRoots:
    """A sidecar path is validated relative; the destination is not.

    Validation proves the declared path is relative and under `.pi/`, which
    says nothing about what the destination looks like at landing time.
    Replace an intermediate directory with a symlink and every landing below
    it follows the link.
    """

    def test_a_symlinked_parent_directory_refuses_the_landing(
        self, clone: pathlib.Path, dest: pathlib.Path, tmp_path: pathlib.Path
    ) -> None:
        sidecar(clone, ".pi/agent/intercom/config.json", "{}")
        outside = tmp_path / "outside"
        outside.mkdir()
        (dest / "intercom").symlink_to(outside)

        with pytest.raises(SystemExit, match="outside the landing roots"):
            pi_config.land_sidecars(
                str(clone),
                str(dest),
                [row(".pi/agent/intercom/config.json", "copy")],
            )

        assert not (outside / "config.json").exists()

    def test_a_real_nested_directory_still_lands(
        self, clone: pathlib.Path, dest: pathlib.Path
    ) -> None:
        sidecar(clone, ".pi/agent/intercom/config.json", "{}")

        pi_config.land_sidecars(
            str(clone), str(dest), [row(".pi/agent/intercom/config.json", "copy")]
        )

        assert (dest / "intercom" / "config.json").read_text() == "{}"


class TestProveSidecarsSourceRequiresTracking:
    """A present but untracked sidecar passes every local gate and is absent
    from the commit, so a fresh clone cannot deploy. .gitignore cannot catch
    it: the file is neither ignored nor added."""

    def test_an_untracked_present_sidecar_fails(self, clone: pathlib.Path) -> None:
        sidecar(clone, ".pi/agent/thing.json", "{}")

        with pytest.raises(SystemExit, match="untracked"):
            pi_config.prove_sidecars_source(
                str(clone), [row(".pi/agent/thing.json", "copy")]
            )

    def test_a_tracked_sidecar_passes(self, clone: pathlib.Path) -> None:
        sidecar(clone, ".pi/agent/thing.json", "{}")
        commit(clone)

        pi_config.prove_sidecars_source(
            str(clone), [row(".pi/agent/thing.json", "copy")]
        )

    def test_an_optional_absent_sidecar_still_passes(self, clone: pathlib.Path) -> None:
        """Absent is a state; untracked-but-present is a mistake."""
        pi_config.prove_sidecars_source(
            str(clone), [row(".pi/agent/absent.json", "copy", required=False)]
        )
