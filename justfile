# Host landing for this source tree.
# Nix installs the pi binary. home/ mirrors $HOME, so every payload path
# states its own destination. Static payloads are copied. Files the runtime
# mutates but this repo tracks (settings.json, keybindings.json, classified
# plugin sidecars) are symlinked so writes go through to git.

src := justfile_directory()

# List available recipes
default:
    @just --list

# Install the git hooks for every stage .pre-commit-config.yaml declares
hooks:
    pre-commit install --install-hooks

# Run every gate over the whole tree
lint:
    pre-commit run --all-files

# Prove the devShell supplies every tool a recipe, a hook, or an LSP this tree uses
devshell-check:
    #!/usr/bin/env bash
    set -euo pipefail
    missing=()
    for t in just pre-commit python3 node dprint ruff typos committed \
             gitleaks ripsecrets lychee editorconfig-checker nixfmt \
             statix deadnix jq pyright-langserver nixd yaml-language-server \
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
    #!/usr/bin/env bash
    set -euo pipefail
    src="{{ src }}"
    payload="$src/home"
    agent_src="$payload/.pi/agent"
    dest="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"

    store_owned() {
      local p="$1"
      [ -L "$p" ] || return 1
      local t
      t="$(readlink -f "$p" 2>/dev/null || readlink "$p")"
      case "$t" in
        */nix/store*) return 0 ;;
      esac
      return 1
    }

    mkdir -p "$dest"
    dest="$(cd "$dest" && pwd -P)"

    # Every landing appends one `how<TAB>abs-path` line here, right where it
    # already echoes. A later step turns this into the deploy manifest. The
    # manifest is recorded, never recomputed: a parallel enumeration would have
    # to re-implement the skip rules inside land_sidecars, and each divergence
    # there is a deletion.
    run_manifest="$(mktemp -t pi-config-run.XXXXXX)"
    export PI_CONFIG_RUN_MANIFEST="$run_manifest"
    trap 'rm -f "$run_manifest"' EXIT

    record() {
      printf '%s\t%s\n' "$1" "$2" >>"$PI_CONFIG_RUN_MANIFEST"
    }

    if store_owned "$dest/AGENTS.md" || store_owned "$dest/prompts"; then
      echo "Home Manager still owns $dest (store symlink)." >&2
      echo "Thin the pi-coding-agent module, activate, then rerun just deploy." >&2
      exit 1
    fi
    if store_owned "$dest/settings.json"; then
      echo "Home Manager still owns $dest/settings.json (store symlink)." >&2
      exit 1
    fi

    copy_file() {
      install -m 0644 "$1" "$2"
      record copy "$2"
      echo "copied $2"
    }

    copy_dir_files() {
      local from="$1" to="$2"
      if [ -L "$to" ]; then
        rm -f "$to"
      fi
      mkdir -p "$to"
      record dir "$to"
      local f
      for f in "$from"/*; do
        [ -f "$f" ] || continue
        install -m 0644 "$f" "$to/$(basename "$f")"
        record copy "$to/$(basename "$f")"
        echo "copied $to/$(basename "$f")"
      done
    }

    link_tracked() {
      local from="$1" to="$2"
      if store_owned "$to"; then
        echo "Home Manager still owns $to (store symlink)." >&2
        exit 1
      fi
      if [ -d "$to" ] && [ ! -L "$to" ]; then
        echo "refusing to replace directory $to with a symlink" >&2
        exit 1
      fi
      if [ -e "$to" ] || [ -L "$to" ]; then
        rm -f "$to"
      fi
      ln -sfn "$from" "$to"
      record symlink "$to"
      echo "linked $to -> $from"
    }

    copy_file "$agent_src/AGENTS.md" "$dest/AGENTS.md"
    copy_dir_files "$agent_src/prompts" "$dest/prompts"

    for d in extensions themes skills agents; do
      if [ -d "$agent_src/$d" ]; then
        copy_dir_files "$agent_src/$d" "$dest/$d"
      fi
    done
    if [ -f "$agent_src/APPEND_SYSTEM.md" ]; then
      copy_file "$agent_src/APPEND_SYSTEM.md" "$dest/APPEND_SYSTEM.md"
    fi

    link_tracked "$agent_src/settings.json" "$dest/settings.json"
    if [ -f "$agent_src/keybindings.json" ]; then
      link_tracked "$agent_src/keybindings.json" "$dest/keybindings.json"
    fi
    python3 "$src/scripts/package-pins.py" land-sidecars "$src" "$dest"
    python3 "$src/scripts/package-pins.py" converge "$src" "$dest"

    just doctor

    # Last, because pi remove runs npm and can need the network. A failure
    # here leaves the config correct and only an install tree orphaned.
    python3 "$src/scripts/package-pins.py" converge-trees "$src" "$dest"

# Land, then show what deploy would remove, without removing it
deploy-report:
    PI_CONFIG_PRUNE=report just deploy

# Land, then also remove the unmanaged files a plain deploy only reports.
# One-shot, for a host landed before the deploy manifest existed.
deploy-adopt:
    PI_CONFIG_PRUNE=adopt just deploy

# Prove the source tree, and the landing when dest exists
doctor:
    #!/usr/bin/env bash
    set -euo pipefail
    src="{{ src }}"
    payload="$src/home"
    agent_src="$payload/.pi/agent"
    dest="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"

    fail() { echo "doctor: $*" >&2; exit 1; }
    ok() { echo "ok  $*"; }

    for f in SPEC.md README.md AGENTS.md justfile .gitignore package.json flake.nix .envrc .pre-commit-config.yaml; do
      [ -f "$src/$f" ] || fail "missing $src/$f"
      ok "meta $f"
    done
    [ ! -e "$src/AGENTS.override.md" ] || fail "AGENTS.override.md was replaced by the root AGENTS.md; delete it"

    for f in .pi/agent/settings.json .pi/agent/AGENTS.md .pi/agent/prompts/review.md \
      .pi/agent/extensions/worktree-guard.ts .pi/lsp-client.json; do
      [ -f "$payload/$f" ] || fail "missing $payload/$f"
      ok "payload $f"
    done

    for line in /home/.pi/agent/auth.json /home/.pi/agent/web-search.json \
      /home/.pi/agent/web-search-cache/ /home/.pi/agent/sessions/ \
      /home/.pi/agent/npm/ /home/.pi/agent/git/ /home/.pi/agent/bin/ \
      /home/.pi/agent/models.json /home/.pi/agent/trust.json \
      /home/.pi/agent/intercom/broker.port.json; do
      grep -qxF "$line" "$src/.gitignore" || fail ".gitignore missing $line"
    done
    ok "gitignore lines"

    for p in home/.pi/agent/auth.json home/.pi/agent/web-search.json \
      home/.pi/agent/web-search-cache/foo home/.pi/agent/sessions/foo \
      home/.pi/agent/npm/foo home/.pi/agent/git/foo home/.pi/agent/bin/foo \
      home/.pi/agent/models.json home/.pi/agent/trust.json \
      home/.pi/agent/models-store.json home/.pi/agent/intercom/broker.port.json; do
      git -C "$src" check-ignore -q --no-index "$p" || fail "not ignored: $p"
    done
    ok "check-ignore"

    python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$agent_src/settings.json" || fail "settings.json is not JSON"
    ok "settings.json json"

    python3 "$src/scripts/package-pins.py" prove-sidecars "$src" "$dest" || fail "plugin docs or sidecars"

    if [ -L "$agent_src/AGENTS.md" ]; then
      t="$(readlink -f "$agent_src/AGENTS.md" 2>/dev/null || readlink "$agent_src/AGENTS.md")"
      case "$t" in
        */nix/store*) fail "source payload AGENTS.md is a store symlink" ;;
      esac
    fi
    ok "source payload AGENTS.md not store"

    if [ "${DOCTOR_SOURCE_ONLY:-}" = "1" ]; then
      exit 0
    fi

    if [ -n "${PI_CODING_AGENT_DIR:-}" ]; then
      default="$(cd "$HOME/.pi/agent" 2>/dev/null && pwd -P || echo "$HOME/.pi/agent")"
      resolved="$(cd "$dest" 2>/dev/null && pwd -P || echo "$dest")"
      clone="$(cd "$src" 2>/dev/null && pwd -P || echo "$src")"
      # home/ mirrors $HOME, so home/.pi/agent looks like a valid live dir.
      # It is not. This clone is source. SPEC.md §3 and §15 forbid the move.
      case "$resolved" in
        "$clone" | "$clone"/*)
          fail "PI_CODING_AGENT_DIR points inside this clone ($resolved); the clone is source, not the live dir"
          ;;
      esac
      if [ "$resolved" != "$default" ]; then
        echo "warning: PI_CODING_AGENT_DIR=$PI_CODING_AGENT_DIR (physical $resolved) is not $default" >&2
      fi
    fi

    if [ ! -d "$dest" ]; then
      echo "note: dest $dest does not exist (source-only doctor)"
      exit 0
    fi

    store_owned() {
      local p="$1"
      [ -L "$p" ] || return 1
      local t
      t="$(readlink -f "$p" 2>/dev/null || readlink "$p")"
      case "$t" in
        */nix/store*) return 0 ;;
      esac
      return 1
    }

    linked_to() {
      local p="$1" want="$2" label="$3"
      [ -L "$p" ] || fail "$label is not a symlink"
      store_owned "$p" && fail "$label is a store symlink"
      local got wantp
      got="$(readlink -f "$p")"
      wantp="$(readlink -f "$want")"
      [ "$got" = "$wantp" ] || fail "$label -> $got, want $wantp"
      ok "$label symlink"
    }

    [ -f "$dest/AGENTS.md" ] && [ ! -L "$dest/AGENTS.md" ] || fail "dest AGENTS.md is not a regular file"
    store_owned "$dest/AGENTS.md" && fail "dest AGENTS.md is a store symlink"
    cmp -s "$agent_src/AGENTS.md" "$dest/AGENTS.md" || fail "dest AGENTS.md does not match source"
    ok "dest AGENTS.md copy"

    [ -f "$dest/prompts/review.md" ] && [ ! -L "$dest/prompts/review.md" ] || fail "dest prompts/review.md is not a regular file"
    [ ! -L "$dest/prompts" ] || fail "dest prompts/ is a symlink; want a copied directory"
    cmp -s "$agent_src/prompts/review.md" "$dest/prompts/review.md" || fail "dest prompts/review.md does not match source"
    ok "dest prompts/review.md copy"

    # The worktree guard is a gate, so a stale or missing copy is a silently
    # open gate. Prove the landed file matches the source byte for byte.
    [ -f "$dest/extensions/worktree-guard.ts" ] || fail "dest extensions/worktree-guard.ts is missing"
    [ ! -L "$dest/extensions" ] || fail "dest extensions/ is a symlink; want a copied directory"
    cmp -s "$agent_src/extensions/worktree-guard.ts" "$dest/extensions/worktree-guard.ts" \
      || fail "dest extensions/worktree-guard.ts does not match source"
    ok "dest extensions/worktree-guard.ts copy"

    linked_to "$dest/settings.json" "$agent_src/settings.json" "dest settings.json"
    if [ -f "$agent_src/keybindings.json" ]; then
      linked_to "$dest/keybindings.json" "$agent_src/keybindings.json" "dest keybindings.json"
    fi

    # A stale AGENTS.override.md is no longer named here. The unmanaged scan
    # reports any file deploy did not land, and just deploy-adopt removes it.
    if [ -f "$dest/AGENTS.md" ] && cmp -s "$src/AGENTS.md" "$dest/AGENTS.md"; then
      fail "dest AGENTS.md is the clone-rules file, not the payload"
    fi
    ok "dest carries the payload AGENTS.md, not the clone rules"

    if [ -e "$dest/auth.json" ]; then
      [ -f "$dest/auth.json" ] && [ ! -L "$dest/auth.json" ] || fail "dest auth.json is not a regular file"
      mode="$(stat -c '%a' "$dest/auth.json")"
      [ "$mode" = "600" ] || fail "dest auth.json mode is $mode, want 600"
      ok "dest auth.json mode 600"
    fi

    python3 "$src/scripts/package-pins.py" prove-manifest "$src" "$dest"
    python3 "$src/scripts/package-pins.py" note-trees "$src" "$dest"

# Show source, dest, and whether live files exist
status:
    #!/usr/bin/env bash
    set -euo pipefail
    src="{{ src }}"
    dest="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"
    echo "source $src"
    echo "dest $dest"
    if [ -n "${PI_CODING_AGENT_DIR:-}" ]; then
      echo "PI_CODING_AGENT_DIR $PI_CODING_AGENT_DIR"
    else
      echo "PI_CODING_AGENT_DIR (unset)"
    fi

    describe() {
      local p="$1" name="$2"
      if [ -L "$p" ]; then
        local t
        t="$(readlink -f "$p" 2>/dev/null || readlink "$p")"
        case "$t" in
          */nix/store*) echo "$name store-symlink" ;;
          *) echo "$name symlink $t" ;;
        esac
      elif [ -e "$p" ]; then
        echo "$name file"
      else
        echo "$name no"
      fi
    }

    describe "$dest/AGENTS.md" "dest AGENTS.md"
    describe "$dest/settings.json" "dest settings.json"
    describe "$dest/auth.json" "dest auth.json"
    python3 "$src/scripts/package-pins.py" status "$src" "$dest"
    if command -v pi >/dev/null 2>&1; then
      echo "pi $(command -v pi)"
    else
      echo "pi (missing)"
    fi

# Source-tree proofs (safe without a host landing)
check:
    #!/usr/bin/env bash
    set -euo pipefail
    src="{{ src }}"
    DOCTOR_SOURCE_ONLY=1 just doctor
    git -C "$src" ls-files -z | while IFS= read -r -d '' f; do
      case "$f" in
        home/.pi/agent/auth.json | home/.pi/agent/web-search.json | home/.pi/agent/web-search-cache/* | \
          home/.pi/agent/models.json | home/.pi/agent/trust.json | home/.pi/agent/models-store.json | \
          home/.pi/agent/sessions/* | home/.pi/agent/npm/* | home/.pi/agent/git/* | home/.pi/agent/bin/*)
          echo "tracked secret or install tree: $f" >&2
          exit 1
          ;;
      esac
    done
    echo "ok  no tracked secrets"

    # The guard keys on the word `git`, which is what keeps `wt` and
    # `rk worktree add` open. A widened pattern would refuse the tools the
    # rule routes work into, so the case table is a gate, not a comment.
    node "$src/scripts/check-worktree-guard.mjs"
