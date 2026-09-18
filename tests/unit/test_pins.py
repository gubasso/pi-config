"""Reading a `packages` pin: which package it names, and whether it is frozen.

A pin is the only thing that says which upstream this repository trusts. Get
the name wrong and `docs/plugins/<name>/` points at the wrong findings; get
the freeze detection wrong and an unversioned-pins rule stops being enforced.
"""

from __future__ import annotations

import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


class TestSourceOf:
    def test_reads_a_bare_string(self) -> None:
        assert pi_config.source_of("  npm:pi-thing  ") == "npm:pi-thing"

    def test_reads_the_source_key_of_an_object(self) -> None:
        assert pi_config.source_of({"source": "npm:pi-thing"}) == "npm:pi-thing"

    @pytest.mark.parametrize("entry", [None, 7, [], {}, {"name": "pi-thing"}])
    def test_refuses_anything_else(self, entry: object) -> None:
        with pytest.raises(SystemExit):
            pi_config.source_of(entry)


class TestNpmName:
    @pytest.mark.parametrize(
        ("spec", "want"),
        [
            ("pi-thing", "pi-thing"),
            ("pi-thing@1.2.3", "pi-thing"),
            ("@scope/pi-thing", "@scope/pi-thing"),
            ("@scope/pi-thing@1.2.3", "@scope/pi-thing"),
        ],
    )
    def test_strips_the_version_and_keeps_the_scope(self, spec: str, want: str) -> None:
        assert pi_config.npm_name(spec) == want


class TestParseGit:
    @pytest.mark.parametrize(
        ("source", "want"),
        [
            ("git:github.com/user/repo", ("github.com", "user/repo")),
            ("github.com/user/repo", ("github.com", "user/repo")),
            ("git:github.com/user/repo.git", ("github.com", "user/repo")),
            ("git:github.com/user/repo@v1", ("github.com", "user/repo")),
            ("https://github.com/user/repo", ("github.com", "user/repo")),
            ("ssh://git@github.com/user/repo.git", ("github.com", "user/repo")),
            ("git@github.com:user/repo.git", ("github.com", "user/repo")),
            ("git:localhost/user/repo", ("localhost", "user/repo")),
        ],
    )
    def test_recognises_every_spelling(
        self, source: str, want: tuple[str, str]
    ) -> None:
        assert pi_config.parse_git(source) == want

    @pytest.mark.parametrize(
        "source",
        [
            "npm:pi-thing",
            "pi-thing",
            # A host with no dot is a bare npm name, not a git host.
            "user/repo",
            # A local path, which classify() must route to `local`.
            "./extensions/thing.ts",
            "/abs/path",
        ],
    )
    def test_rejects_what_is_not_a_git_source(self, source: str) -> None:
        assert pi_config.parse_git(source) is None


class TestPluginName:
    @pytest.mark.parametrize(
        ("source", "want"),
        [
            ("npm:pi-web-access", "pi-web-access"),
            ("npm:@scope/pi-thing", "scope-pi-thing"),
            ("npm:PI-Thing", "pi-thing"),
        ],
    )
    def test_derives_an_npm_name(self, source: str, want: str) -> None:
        spec = source[4:]
        got = pi_config.plugin_name(source, "npm", npm=pi_config.npm_name(spec))
        assert got == want

    @pytest.mark.parametrize(
        ("source", "want"),
        [
            ("git:github.com/user/repo", "repo"),
            ("git:github.com/user/repo@v1", "repo"),
            ("git:github.com/Org/Repo", "repo"),
        ],
    )
    def test_derives_a_git_name_from_the_last_segment(
        self, source: str, want: str
    ) -> None:
        git = pi_config.parse_git(source)
        assert git is not None
        assert pi_config.plugin_name(source, "git", git=git) == want

    @pytest.mark.parametrize(
        ("source", "want"),
        [
            ("./extensions/my-thing.ts", "my-thing"),
            ("./extensions/My Thing.js", "my-thing"),
            ("./extensions/thing.json", "thing"),
        ],
    )
    def test_slugs_a_local_path(self, source: str, want: str) -> None:
        assert pi_config.plugin_name(source, "local") == want


class TestFrozenRef:
    @pytest.mark.parametrize(
        ("source", "kind", "want"),
        [
            ("npm:pi-thing", "npm", None),
            ("npm:pi-thing@1.2.3", "npm", "1.2.3"),
            ("npm:@scope/pi-thing", "npm", None),
            ("npm:@scope/pi-thing@1.2.3", "npm", "1.2.3"),
            # A range departs from the unversioned rule without being a
            # freeze in Pi's sense, and must still be reported.
            ("npm:pi-thing@^1", "npm", "^1"),
            ("git:github.com/user/repo", "git", None),
            ("git:github.com/user/repo@v1", "git", "v1"),
            ("git:github.com/user/repo@0123abcd", "git", "0123abcd"),
            ("git@github.com:user/repo.git", "git", None),
        ],
    )
    def test_reports_only_a_real_suffix(
        self, source: str, kind: str, want: str | None
    ) -> None:
        assert pi_config.frozen_ref(source, kind) == want

    def test_an_scp_url_user_is_not_a_ref(self) -> None:
        """`git@host:path` carries an @ that names a user, not a version."""
        assert pi_config.frozen_ref("git@github.com:user/repo", "git") is None

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "frozen_ref strips the git@ user only from the scp form `git@host:path`, "
            "so the URL form `ssh://git@host/user/repo@v2` splits on the user's @ "
            "and reports no ref. parse_git reads the same pin correctly, so the two "
            "disagree and a freeze on this spelling goes unreported."
        ),
    )
    def test_a_frozen_ssh_url_is_reported_as_frozen(self) -> None:
        assert pi_config.parse_git("ssh://git@github.com/user/repo@v2") is not None
        assert pi_config.frozen_ref("ssh://git@github.com/user/repo@v2", "git") == "v2"


class TestClassify:
    def test_an_npm_pin_lands_under_the_npm_tree(self) -> None:
        kind, name, tree = pi_config.classify("npm:pi-thing", "/src", "/dest")
        assert (kind, name) == ("npm", "pi-thing")
        assert tree == "/dest/npm/node_modules/pi-thing"

    def test_a_git_pin_lands_under_host_and_path(self) -> None:
        kind, name, tree = pi_config.classify(
            "git:github.com/user/repo", "/src", "/dest"
        )
        assert (kind, name) == ("git", "repo")
        assert tree == "/dest/git/github.com/user/repo"

    def test_a_relative_local_pin_resolves_against_the_payload(self) -> None:
        kind, name, tree = pi_config.classify("./extensions/x.ts", "/src", "/dest")
        assert (kind, name) == ("local", "x")
        assert tree == "/src/extensions/x.ts"

    def test_an_empty_dest_yields_no_tree(self) -> None:
        """Source-only runs have no destination to name a tree under."""
        _, _, tree = pi_config.classify("npm:pi-thing", "/src", "")
        assert tree == ""
