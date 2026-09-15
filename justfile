# Host landing for this source tree.
# Nix installs the pi binary. These recipes copy owned files into the
# directory Pi already reads and prove the contract.

src := justfile_directory()

# List available recipes
default:
    @just --list

# Copy owned artifacts into the live agent directory
deploy *args:
    #!/usr/bin/env bash
    set -euo pipefail
    src="{{src}}"
    dest="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"
    force_settings=0
    if [ "${1:-}" = "--settings" ]; then
      force_settings=1
    elif [ -n "${1:-}" ]; then
      echo "unknown argument: $1 (expected --settings)" >&2
      exit 1
    fi

    store_owned() {
      local p="$1"
      [ -e "$p" ] || [ -L "$p" ] || return 1
      if [ -L "$p" ]; then
        local t
        t="$(readlink -f "$p" 2>/dev/null || readlink "$p")"
        case "$t" in
          */nix/store*) return 0 ;;
        esac
      fi
      return 1
    }

    mkdir -p "$dest"

    if store_owned "$dest/AGENTS.md" || store_owned "$dest/prompts"; then
      echo "Home Manager still owns $dest (store symlink)." >&2
      echo "Thin the pi-coding-agent module, activate, then rerun just deploy." >&2
      exit 1
    fi
    if [ -e "$dest/settings.json" ] || [ -L "$dest/settings.json" ]; then
      if store_owned "$dest/settings.json"; then
        echo "Home Manager still owns $dest/settings.json (store symlink)." >&2
        echo "Thin the pi-coding-agent module, activate, then rerun just deploy." >&2
        exit 1
      fi
    fi

    copy_file() {
      install -m 0644 "$1" "$2"
      echo "wrote $2"
    }

    copy_dir_files() {
      local from="$1" to="$2"
      mkdir -p "$to"
      local f
      for f in "$from"/*; do
        [ -f "$f" ] || continue
        install -m 0644 "$f" "$to/$(basename "$f")"
        echo "wrote $to/$(basename "$f")"
      done
    }

    copy_file "$src/AGENTS.md" "$dest/AGENTS.md"
    copy_dir_files "$src/prompts" "$dest/prompts"

    for d in extensions themes skills agents; do
      if [ -d "$src/$d" ]; then
        copy_dir_files "$src/$d" "$dest/$d"
      fi
    done
    if [ -f "$src/APPEND_SYSTEM.md" ]; then
      copy_file "$src/APPEND_SYSTEM.md" "$dest/APPEND_SYSTEM.md"
    fi

    if [ ! -e "$dest/keybindings.json" ] && [ -f "$src/keybindings.json" ]; then
      copy_file "$src/keybindings.json" "$dest/keybindings.json"
    fi
    if [ "$force_settings" -eq 1 ] || [ ! -e "$dest/settings.json" ]; then
      copy_file "$src/settings.json" "$dest/settings.json"
    fi

    just doctor

# Prove the source tree, and the landing when dest exists
doctor:
    #!/usr/bin/env bash
    set -euo pipefail
    src="{{src}}"
    dest="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"

    fail() { echo "doctor: $*" >&2; exit 1; }
    ok() { echo "ok  $*"; }

    for f in SPEC.md settings.json AGENTS.md AGENTS.override.md prompts/review.md .gitignore package.json; do
      [ -f "$src/$f" ] || fail "missing $src/$f"
      ok "source $f"
    done

    for line in auth.json sessions/ npm/ git/ bin/ models.json trust.json; do
      grep -qxF "$line" "$src/.gitignore" || fail ".gitignore missing $line"
    done
    ok "gitignore lines"

    for p in auth.json sessions/foo npm/foo git/foo bin/foo models.json trust.json models-store.json; do
      git -C "$src" check-ignore -q --no-index "$p" || fail "not ignored: $p"
    done
    ok "check-ignore"

    python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$src/settings.json" || fail "settings.json is not JSON"
    ok "settings.json json"

    if [ -L "$src/AGENTS.md" ]; then
      t="$(readlink -f "$src/AGENTS.md" 2>/dev/null || readlink "$src/AGENTS.md")"
      case "$t" in
        */nix/store*) fail "source AGENTS.md is a store symlink" ;;
      esac
    fi
    ok "source AGENTS.md not store"

    if [ "${DOCTOR_SOURCE_ONLY:-}" = "1" ]; then
      exit 0
    fi

    if [ -n "${PI_CODING_AGENT_DIR:-}" ]; then
      default="$(cd "$HOME/.pi/agent" 2>/dev/null && pwd -P || echo "$HOME/.pi/agent")"
      resolved="$(cd "$dest" 2>/dev/null && pwd -P || echo "$dest")"
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

    [ -f "$dest/AGENTS.md" ] && [ ! -L "$dest/AGENTS.md" ] || fail "dest AGENTS.md is not a regular file"
    store_owned "$dest/AGENTS.md" && fail "dest AGENTS.md is a store symlink"
    cmp -s "$src/AGENTS.md" "$dest/AGENTS.md" || fail "dest AGENTS.md does not match source"
    ok "dest AGENTS.md"

    [ -f "$dest/prompts/review.md" ] && [ ! -L "$dest/prompts/review.md" ] || fail "dest prompts/review.md is not a regular file"
    cmp -s "$src/prompts/review.md" "$dest/prompts/review.md" || fail "dest prompts/review.md does not match source"
    ok "dest prompts/review.md"

    [ -f "$dest/settings.json" ] && [ ! -L "$dest/settings.json" ] || fail "dest settings.json is not a regular file"
    ok "dest settings.json"

    [ ! -e "$dest/AGENTS.override.md" ] || fail "dest AGENTS.override.md must not exist"
    ok "dest has no AGENTS.override.md"

    if [ -e "$dest/auth.json" ]; then
      [ -f "$dest/auth.json" ] && [ ! -L "$dest/auth.json" ] || fail "dest auth.json is not a regular file"
      mode="$(stat -c '%a' "$dest/auth.json")"
      [ "$mode" = "600" ] || fail "dest auth.json mode is $mode, want 600"
      ok "dest auth.json mode 600"
    fi

# Show source, dest, and whether live files exist
status:
    #!/usr/bin/env bash
    set -euo pipefail
    src="{{src}}"
    dest="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"
    echo "source $src"
    echo "dest $dest"
    if [ -n "${PI_CODING_AGENT_DIR:-}" ]; then
      echo "PI_CODING_AGENT_DIR $PI_CODING_AGENT_DIR"
    else
      echo "PI_CODING_AGENT_DIR (unset)"
    fi
    if [ -L "$dest/AGENTS.md" ]; then
      t="$(readlink -f "$dest/AGENTS.md" 2>/dev/null || readlink "$dest/AGENTS.md")"
      case "$t" in
        */nix/store*) echo "dest AGENTS.md store-symlink" ;;
        *) echo "dest AGENTS.md symlink" ;;
      esac
    elif [ -e "$dest/AGENTS.md" ]; then
      echo "dest AGENTS.md yes"
    else
      echo "dest AGENTS.md no"
    fi
    if [ -e "$dest/settings.json" ]; then
      echo "dest settings.json yes"
    else
      echo "dest settings.json no"
    fi
    if [ -e "$dest/auth.json" ]; then
      echo "dest auth.json yes"
    else
      echo "dest auth.json no"
    fi
    if command -v pi >/dev/null 2>&1; then
      echo "pi $(command -v pi)"
    else
      echo "pi (missing)"
    fi

# Source-tree proofs (safe without a host landing)
check:
    #!/usr/bin/env bash
    set -euo pipefail
    src="{{src}}"
    DOCTOR_SOURCE_ONLY=1 just doctor
    git -C "$src" ls-files -z | while IFS= read -r -d '' f; do
      case "$f" in
        auth.json|models.json|trust.json|models-store.json|sessions/*|npm/*|git/*|bin/*)
          echo "tracked secret or install tree: $f" >&2
          exit 1
          ;;
      esac
    done
    echo "ok  no tracked secrets"
