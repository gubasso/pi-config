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
            # Every package here backs a recipe in the justfile or a
            # `language: system` hook in .pre-commit-config.yaml. A system
            # hook resolves off PATH and gets no environment of its own, so
            # this list is the only thing that can supply it. `just
            # devshell-check` is the executable form of that claim.
            packages = with pkgs; [
              # The landing contract: deploy, doctor, status, check.
              just
              # The gate runner.
              pre-commit
              # scripts/package-pins.py, and the doctor's JSON probes.
              python3
              # markdownlint-cli2 runs on this node through
              # `language_version: system`. pre-commit's own nodeenv
              # downloads a generic-glibc node whose ELF interpreter
              # /lib64/ld-linux-x86-64.so.2 does not exist on this host.
              nodejs
              # The formatter of record for markdown and JSON. dprint.json
              # lists what it must not touch.
              dprint
              # scripts/package-pins.py.
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
            ];

            # The greeting goes to standard error, because `nix develop
            # --command` shares the command's stdout: on stdout this banner
            # is prepended to whatever the command emits, which silently
            # corrupts every redirected artifact.
            shellHook = ''echo "pi-config dev shell ready" >&2'';
          };
        }
      );
    };
}
