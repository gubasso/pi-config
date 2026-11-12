{
  description = "pi-config — source of truth for the global Pi agent config";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    # The store guard of the canon (exobrain): `exobrain store-guard --daily`
    # in .envrc warns about working-tree copies in the Nix store.
    exobrain-tech = {
      url = "github:gubasso/exobrain-tech/v1.1.0";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  # `...` is required: Nix always applies `outputs (inputs // { self = …; })`,
  # so a closed attrset breaks the flake the moment `self` is unused and gets
  # dropped. Keep it even when no extra argument is consumed.
  outputs =
    { nixpkgs, exobrain-tech, ... }:
    let
      # One system: the host this repository lands onto. Grow the list
      # together with a machine that runs the gates natively.
      systems = [
        "x86_64-linux"
      ];
      # `genAttrs systems` already takes the per-system function, so the
      # wrapping lambda statix would flag is left off.
      eachSystem = nixpkgs.lib.genAttrs systems;
    in
    {
      # `nix fmt` uses the RFC 166 formatter, which is also on PATH for the
      # nixfmt pre-commit hook. `nixfmt-rfc-style` is a deprecated alias.
      formatter = eachSystem (system: nixpkgs.legacyPackages.${system}.nixfmt);

      devShells = eachSystem (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          # The one Python of the shell. pyproject.toml bounds it with
          # requires-python.
          python = pkgs.python3;
        in
        {
          default = pkgs.mkShell {
            # Each dependency has one owner, the most specific file that
            # declares it natively. pyproject.toml and uv.lock own the Python
            # package and its dev tools, package.json and package-lock.json
            # own the TypeScript tools, and .pre-commit-config.yaml owns each
            # hook tool that the hook runner can build. The host supplies the
            # hook runner prek. This list holds the
            # toolchains, the runners, and each tool that no owner above can
            # declare, such as the language servers the agent uses on this
            # tree. `just devshell-check` makes sure each tool is on PATH.
            packages = with pkgs; [
              # The landing contract: deploy, doctor, status, check.
              just
              # The interpreter and the manager of the Python package. The
              # shellHook syncs uv.lock into .venv.
              python
              uv
              # The toolchain that the hook runner builds the rust hooks with,
              # ripsecrets and deadnix, on a machine with no cargo. prek takes
              # it from PATH and downloads none.
              cargo
              rustc
              # markdownlint-cli2 runs on this node through
              # `language_version: system`, so the hook runner downloads no
              # node. A downloaded generic-glibc node needs the ELF interpreter
              # /lib64/ld-linux-x86-64.so.2, which does not exist on this host.
              nodejs
              # Builds node_modules from package-lock.json and links it into
              # the tree. See the npmDeps attribute and the shellHook below.
              importNpmLock.hooks.linkNodeModulesHook
              # tests/e2e/: the justfile recipes, driven as a person drives
              # them. The three libraries carry `assert_output`,
              # `assert_success`, and the file predicates.
              (bats.withLibraries (p: [
                p.bats-support
                p.bats-assert
                p.bats-file
              ]))
              # The formatter of record for markdown, JSON, and TypeScript,
              # which has no hook in a language that the hook runner builds.
              # dprint.json lists what it must not touch.
              dprint
              # The link check of the pre-push stage (lychee-system).
              lychee
              # The RFC 166 formatter, which `nix fmt` and the nixfmt hook
              # share, and statix, which has no hook that the hook runner builds.
              nixfmt
              statix
              jq
              # exobrain, the store guard that .envrc runs once a day.
              exobrain-tech.packages.${system}.default
              # Language servers pi-lsp-client probes on PATH for the
              # languages this repository actually contains. Do not add a
              # server for a language that is not here.
              # .py types: `pyright-langserver` comes from the dev group of
              # pyproject.toml, in .venv.
              nixd # .nix
              yaml-language-server # .pre-commit-config.yaml
              bash-language-server # .envrc and justfile recipes
              taplo # .toml (`taplo lsp stdio`); not a pi-lsp-client builtin
              vscode-langservers-extracted # .json/.jsonc
              marksman # .md; not a pi-lsp-client builtin
            ];

            # node_modules, built by Nix from package-lock.json. There is no
            # hash to compute here and none to re-compute on a bump: the
            # lockfile is the pin. `npmRoot` is read at evaluation time for
            # package.json and package-lock.json only, and the derivation
            # sets `dontUnpack`, so nothing else in this tree is an input
            # and an unrelated edit does not rebuild it.
            #
            # vitest therefore reaches PATH the same way every other gate
            # tool does, which keeps the §14 rule intact: no test runner is
            # installed by hand, and a fresh clone is ready after `direnv
            # allow` with no npm step.
            npmDeps = pkgs.importNpmLock.buildNodeModules {
              npmRoot = ./.;
              inherit (pkgs) nodejs;
            };

            # Two things this hook needs, and neither is automatic.
            #
            # linkNodeModulesHook installs itself as the shell hook only
            # when `shellHook` is unset, so setting one here would silently
            # drop node_modules. Call it by name instead.
            #
            # It also narrates to stdout. `nix develop --command` shares the
            # command's stdout, so that narration is prepended to whatever
            # the command emits and corrupts every redirected artifact.
            # Both the hook and the greeting go to standard error.
            #
            # `.pi-types` is how `tsc` resolves the one import the payload
            # extensions carry, `@earendil-works/pi-coding-agent`. The types
            # come from the same nixpkgs pin as everything else, so they can
            # never drift from the Pi this shell describes. Taking them from
            # npm instead would pull 167 packages, a second pin of Pi, and an
            # esbuild that does not build in the sandbox. The symlink is
            # gitignored and tsconfig.json maps the module onto it.
            #
            # `npm install --package-lock-only` still drops its install-state
            # marker at node_modules/.package-lock.json once that directory
            # exists. It is a regular file, so the link script reads it as
            # something a person put there and refuses to touch it, printing a
            # refusal on every shell entry. Nix owns this tree, so the marker
            # describes nothing. Drop it before linking.
            #
            # The Python half hands the interpreter of the flake to uv,
            # forbids interpreter downloads, installs uv.lock into .venv as
            # it is, and puts .venv/bin first on PATH. After a change of
            # pyproject.toml, run `uv lock`, then `direnv reload`.
            shellHook = ''
              root="$(git rev-parse --show-toplevel)"
              export UV_PYTHON="${python}/bin/python3"
              export UV_PYTHON_DOWNLOADS=never
              export UV_PROJECT_ENVIRONMENT="$root/.venv"
              uv sync --frozen --quiet --project "$root" >&2 \
                || echo "uv sync failed: after a change of pyproject.toml, run uv lock" >&2
              export VIRTUAL_ENV="$root/.venv"
              export PATH="$root/.venv/bin:$PATH"
              rm -f node_modules/.package-lock.json
              linkNodeModulesHook >&2
              ln -sfn ${pkgs.pi-coding-agent}/lib/node_modules/pi-monorepo .pi-types
              echo "pi-config dev shell ready" >&2
            '';
          };
        }
      );
    };
}
