{
  description = "pi-config — source of truth for the global Pi agent config";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  # `...` is required: Nix always applies `outputs (inputs // { self = …; })`,
  # so a closed attrset breaks the flake the moment `self` is unused and gets
  # dropped. Keep it even when no extra argument is consumed.
  outputs =
    { nixpkgs, ... }:
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
        in
        {
          default = pkgs.mkShell {
            # Every package here backs a recipe, a `language: system` hook,
            # or a language server the agent uses on this tree. A system
            # hook resolves off PATH and gets no environment of its own, so
            # this list is the only thing that can supply it. `just
            # devshell-check` is the executable form of that claim.
            packages = with pkgs; [
              # The landing contract: deploy, doctor, status, check.
              just
              # The gate runner.
              pre-commit
              # scripts/pi_config/, the doctor's JSON probes, and the
              # Python half of the test suite. pytest rides along with the
              # interpreter so no test runner reaches PATH from outside Nix.
              (python3.withPackages (ps: [
                ps.pytest
                # tests/meta reads .pre-commit-config.yaml to prove the
                # formatter and the whitespace fixers skip the same files.
                ps.pyyaml
              ]))
              # markdownlint-cli2 runs on this node through
              # `language_version: system`. pre-commit's own nodeenv
              # downloads a generic-glibc node whose ELF interpreter
              # /lib64/ld-linux-x86-64.so.2 does not exist on this host.
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
              # scripts/run-tests.sh and tests/helpers/*.bash are the only
              # shell this tree authors. Nothing linted them before.
              shellcheck
              shfmt
              # `tsc --noEmit` over tsconfig.json, for the payload
              # extensions and the vitest suite.
              typescript
              # The formatter of record for markdown, JSON, and TypeScript.
              # dprint.json lists what it must not touch.
              dprint
              # scripts/pi_config/ and tests/**/*.py (CLI + `ruff server`).
              ruff
              typos
              committed
              gitleaks
              ripsecrets
              lychee
              editorconfig-checker
              # RFC 166 formatter, plus the two nix linters the hooks call.
              nixfmt
              statix
              deadnix
              jq
              # Language servers pi-lsp-client probes on PATH for the
              # languages this repository actually contains. Do not add a
              # server for a language that is not here.
              pyright # .py types (`pyright-langserver`)
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
            shellHook = ''
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
