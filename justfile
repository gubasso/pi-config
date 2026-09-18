# Host landing for this source tree.
# Nix installs the pi binary. home/ mirrors $HOME, so every payload path
# states its own destination. Static payloads are copied. Files the runtime
# mutates but this repo tracks (settings.json, keybindings.json, classified
# plugin sidecars) are symlinked so writes go through to git.

src := justfile_directory()

# Every recipe reaches the engine as `python3 -m pi_config`, so scripts/ has
# to be importable. Setting it here means one declaration rather than one per
# call site, and it is also what lets the test suite import the same module
# the recipes run.
export PYTHONPATH := src / "scripts"

# List available recipes
default:
    @just --list

# Install the git hooks for every stage .pre-commit-config.yaml declares
hooks:
    pre-commit install --install-hooks

# Run every gate over the whole tree
lint:
    pre-commit run --all-files

# Run the tests a commit must pass
#
# The hook is the source of truth for when the suite runs, so these recipes
# call pre-commit rather than the runner. To drive one slice while you are
# writing it, call the runner directly: `scripts/run-tests.sh fast unit`, or
# `pytest tests/unit -k veto`. That is debugging, and it is not the gate.
test:
    pre-commit run --all-files pi-config-test-fast

# Run the tests a push must pass
test-slow:
    pre-commit run --all-files --hook-stage pre-push pi-config-test-slow

# Run every test, at both budgets
test-all: test test-slow

# Prove the devShell supplies every tool a recipe, a hook, or an LSP this tree uses
devshell-check:
    #!/usr/bin/env bash
    set -euo pipefail
    missing=()
    for t in just pre-commit python3 node dprint ruff typos committed \
             gitleaks ripsecrets lychee editorconfig-checker nixfmt \
             statix deadnix jq pytest bats vitest shellcheck shfmt tsc \
             pyright-langserver nixd yaml-language-server \
             bash-language-server taplo vscode-json-language-server marksman; do
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
    python3 -m pi_config deploy "{{ src }}" "${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"

# Land, then show what deploy would remove, without removing it
deploy-report:
    PI_CONFIG_PRUNE=report just deploy

# Land, then also remove the unmanaged files a plain deploy only reports.
# One-shot, for a host landed before the deploy manifest existed.
deploy-adopt:
    PI_CONFIG_PRUNE=adopt just deploy

# Prove the source tree, and the landing when dest exists
doctor:
    python3 -m pi_config doctor "{{ src }}" "${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"

# Show source, dest, and whether live files exist
status:
    python3 -m pi_config status "{{ src }}" "${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"

# Source-tree proofs (safe without a host landing)
check:
    python3 -m pi_config check "{{ src }}" "${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"
