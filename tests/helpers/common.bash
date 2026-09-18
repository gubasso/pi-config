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

# The operator's real home, captured now.
#
# This file is loaded from `setup()`, before `pi_setup` replaces $HOME, so
# now is the only moment the real value is still readable. Resolving it later
# would read the throwaway home and the guard below would pass on anything.
if [ -z "${PI_REAL_HOME:-}" ]; then
  if [ -z "${HOME:-}" ] || [ ! -d "$HOME" ]; then
    echo "cannot resolve the real home directory; refusing to run" >&2
    exit 1
  fi
  PI_REAL_HOME="$(cd "$HOME" && pwd -P)"
  export PI_REAL_HOME
fi

# Refuse to run against anything inside the operator's real home.
#
# Every other guard in this file is convenience. This one is the reason the
# file exists: a mistake here points the prune engine at real credentials.
pi_guard_dest() {
  local resolved
  resolved="$(cd "$1" 2>/dev/null && pwd -P || echo "$1")"

  case "$resolved" in
  "$PI_REAL_HOME" | "$PI_REAL_HOME"/*)
    echo "refusing to test against $resolved, inside the real home $PI_REAL_HOME" >&2
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
  # Detach from the repository git may have handed us.
  #
  # A pre-push hook runs inside `git push`, and a pre-commit hook inside
  # `git commit`. Both export GIT_INDEX_FILE and GIT_DIR pointing at the real
  # repository. A test that then runs `git add` in its sandbox writes through
  # to the real index, replacing the operator's staged state with the
  # sandbox's. Nothing reports it, and the damage is outside the test.
  unset GIT_INDEX_FILE GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_PREFIX
  unset GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES

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

# A throwaway copy of this source tree, with its own git history.
#
# Several recipes read git: `doctor` asks `check-ignore`, and `check` walks
# `ls-files`. So a copy is not enough, it needs to be a repository. Prune and
# adopt tests also have to delete a payload file, which must never happen in
# the tree the test itself runs from.
#
# The copy takes every tracked path from the working tree rather than from
# HEAD, so a test covers the edit in front of you and not the last commit.
pi_sandbox_repo() {
  local dst="$BATS_TEST_TMPDIR/repo"
  mkdir -p "$dst"
  git -C "$PI_REPO" ls-files -z |
    tar -C "$PI_REPO" --null --files-from=- -cf - |
    tar -C "$dst" -xf -

  git -C "$dst" init -q
  git -C "$dst" add -A
  git -C "$dst" -c user.email=t@example.invalid -c user.name=t commit -qm sandbox

  export PI_SRC="$dst"
  echo "$dst"
}

# Run a justfile recipe against the throwaway destination.
#
# PI_SRC is the sandbox when a test made one, and this tree otherwise.
pi_just() {
  pi_guard_dest "$PI_CODING_AGENT_DIR" || return 1
  local src="${PI_SRC:-$PI_REPO}"
  just --justfile "$src/justfile" --working-directory "$src" "$@"
}

# The payload directory inside whichever tree pi_just is driving.
pi_payload() {
  echo "${PI_SRC:-$PI_REPO}/home/.pi/agent"
}

# Every argument the stub `pi` saw, one call per line.
pi_stub_calls() {
  cat "$PI_STUB_LOG"
}
