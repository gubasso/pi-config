# Shared setup for every bats file in this tree.
#
# bats drives the justfile recipes the way a person drives them, which means
# these tests run the real deploy. Deploy creates, links, and deletes files
# under the live agent directory. So the first job here is making sure the
# live agent directory is a throwaway one.
#
# Call `pi_setup` from `setup()` in every file. It is not optional, and
# `pi_guard_dest` refuses the run rather than trusting that it was called.

# Assertions and file predicates come from the devShell, through
# bats.withLibraries in flake.nix.
bats_load_library bats-support
bats_load_library bats-assert
bats_load_library bats-file

# The source tree under test.
PI_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
export PI_REPO

# Refuse to run against anything inside the operator's real home.
#
# Every other guard in this file is convenience. This one is the reason the
# file exists: a mistake here points the prune engine at real credentials.
pi_guard_dest() {
  local real resolved
  real="$(cd "$(getent passwd "$(id -u)" | cut -d: -f6)" && pwd -P)"
  resolved="$(cd "$1" 2>/dev/null && pwd -P || echo "$1")"

  case "$resolved" in
  "$real" | "$real"/*)
    echo "refusing to test against $resolved, inside the real home $real" >&2
    return 1
    ;;
  esac
  return 0
}

# A throwaway HOME, a live agent directory inside it, and a stub `pi`.
#
# The destination is deliberately not created. Several tests watch what
# creates it, and `just doctor` has a documented source-only path that
# depends on it being absent.
pi_setup() {
  export HOME="$BATS_TEST_TMPDIR/home"
  export PI_CODING_AGENT_DIR="$HOME/.pi/agent"
  mkdir -p "$HOME"

  pi_guard_dest "$HOME" || return 1

  # `pi remove` runs at the end of a deploy. The stub records its arguments
  # so a test can assert convergence without a package tree on disk.
  export PI_STUB_LOG="$BATS_TEST_TMPDIR/pi-calls.log"
  : >"$PI_STUB_LOG"
  export PATH="$PI_REPO/tests/helpers/stubs:$PATH"

  # git needs an identity for anything that commits, and a HOME with no
  # config is exactly what we just built.
  export GIT_CONFIG_GLOBAL="$BATS_TEST_TMPDIR/gitconfig"
  : >"$GIT_CONFIG_GLOBAL"
}

# Run a justfile recipe against the throwaway destination.
pi_just() {
  pi_guard_dest "$PI_CODING_AGENT_DIR" || return 1
  just --justfile "$PI_REPO/justfile" --working-directory "$PI_REPO" "$@"
}

# Every argument the stub `pi` saw, one call per line.
pi_stub_calls() {
  cat "$PI_STUB_LOG"
}
