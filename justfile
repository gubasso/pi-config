# Host landing for this source tree.
# Nix installs the pi binary. home/ mirrors $HOME, so every payload path
# states its own destination. Static payloads are copied. Files the runtime
# mutates but this repo tracks (settings.json, keybindings.json, classified
# plugin sidecars) are symlinked so writes go through to git.

src := justfile_directory()

# The host tools that every recipe needs, checked once before any recipe
# runs: the hooks and the deploy, doctor, status, and check commands read the
# tree through git. host-requirements.toml declares them. The checker comes
# from the devshell, so each check runs through it, and a host without nix
# fails with nix named by the shell.
dev := "nix develop --command"
_host := shell("nix develop --command exobrain host-check nix git")

# List available recipes
default:
    @just --list

# Install the git hooks for every stage .pre-commit-config.yaml declares
hooks:
    {{ dev }} exobrain host-check prek
    prek install --prepare-hooks

# Run every gate over the whole tree
lint:
    {{ dev }} exobrain host-check prek
    prek run --all-files

# Run the tests a commit must pass
#
# The hook is the source of truth for when the suite runs, so these recipes
# call the hook runner prek rather than the test runner. To drive one slice while you are
# writing it, call the runner directly: `scripts/run-tests.sh fast unit`, or
# `uv run pytest tests/unit -k veto`. That is debugging, and it is not the gate.
test:
    {{ dev }} exobrain host-check prek
    prek run --all-files pi-config-test-fast

# Run the tests a push must pass
test-slow:
    {{ dev }} exobrain host-check prek
    prek run --all-files --hook-stage pre-push pi-config-test-slow

# Run every test, at both budgets
test-all: test test-slow

# Prove that the devShell and its owners put every tool a recipe, a hook, or an LSP uses on PATH
devshell-check:
    #!/usr/bin/env bash
    set -euo pipefail
    missing=()
    # The devShell packages, then the tools that .venv (uv.lock) and
    # node_modules (package-lock.json) put on PATH, which a recipe, a hook,
    # or a language server calls.
    for t in just python3 uv node cargo dprint lychee nixfmt statix jq bats exobrain \
             nixd yaml-language-server bash-language-server taplo \
             vscode-json-language-server marksman \
             pytest ruff pyright-langserver vitest tsc; do
      if command -v "$t" >/dev/null 2>&1; then
        echo "ok  $t"
      else
        missing+=("$t")
      fi
    done
    if [ ${#missing[@]} -gt 0 ]; then
      echo "missing from PATH: ${missing[*]}" >&2
      echo "add them to flake.nix and re-enter the devShell" >&2
      exit 1
    fi

# Land owned artifacts into the live agent directory
deploy:
    uv run python -m pi_config deploy "{{ src }}" "${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"

# Land, then show what deploy would remove, without removing it
deploy-report:
    PI_CONFIG_PRUNE=report just deploy

# Land, then also remove the unmanaged files a plain deploy only reports.
# One-shot, for a host landed before the deploy manifest existed.
deploy-adopt:
    PI_CONFIG_PRUNE=adopt just deploy

# Prove the source tree, and the landing when dest exists
doctor:
    uv run python -m pi_config doctor "{{ src }}" "${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"

# Show source, dest, and whether live files exist
status:
    uv run python -m pi_config status "{{ src }}" "${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"

# Source-tree proofs (safe without a host landing)
check:
    uv run python -m pi_config check "{{ src }}" "${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"
