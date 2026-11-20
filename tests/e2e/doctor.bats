#!/usr/bin/env bats
# bats file_tags=slow,local,ci
#
# What `just doctor` and `just check` prove, and what they refuse to pass.
#
# doctor proves the source tree always, and the landing when a destination
# exists. check is the subset that is safe with no host landing at all, which
# is why a pre-commit hook can call it.
#
# Characterization: no test here may be edited to make a refactor pass.

setup() {
  load "../helpers/common.bash"
  pi_setup
  pi_sandbox_repo >/dev/null
}

@test "doctor passes on the source tree with no destination" {
  assert_dir_not_exist "$PI_CODING_AGENT_DIR"

  run pi_just doctor
  assert_success
  assert_output --partial "does not exist (source-only doctor)"
}

@test "doctor proves a landed destination" {
  run pi_just deploy
  assert_success

  run pi_just doctor
  assert_success
  assert_output --partial "dest AGENTS.md copy"
  assert_output --partial "dest settings.json symlink"
}

@test "doctor fails when the settings symlink points somewhere else" {
  run pi_just deploy
  assert_success

  echo '{}' >"$BATS_TEST_TMPDIR/decoy.json"
  ln -sfn "$BATS_TEST_TMPDIR/decoy.json" "$PI_CODING_AGENT_DIR/settings.json"

  run pi_just doctor
  assert_failure
  assert_output --partial "dest settings.json"
}

@test "doctor fails when the destination holds a copy instead of a link" {
  run pi_just deploy
  assert_success

  rm "$PI_CODING_AGENT_DIR/settings.json"
  echo '{}' >"$PI_CODING_AGENT_DIR/settings.json"

  run pi_just doctor
  assert_failure
  assert_output --partial "is not a symlink"
}

@test "doctor fails when the destination carries the clone rules" {
  run pi_just deploy
  assert_success

  # The root AGENTS.md is machinery. Landing it would give the agent this
  # repository's rules on every project it opens.
  cp "$PI_SRC/AGENTS.md" "$PI_CODING_AGENT_DIR/AGENTS.md"

  run pi_just doctor
  assert_failure

  # The content comparison against the payload runs first and catches this,
  # so the dedicated clone-rules message is only reachable when the payload
  # and the clone rules are byte-identical. Both are failures; assert the
  # one doctor actually reports.
  assert_output --partial "dest AGENTS.md does not match source"
}

@test "doctor fails when auth.json is not owner-only" {
  run pi_just deploy
  assert_success

  printf '{"token":"secret"}' >"$PI_CODING_AGENT_DIR/auth.json"
  chmod 644 "$PI_CODING_AGENT_DIR/auth.json"

  run pi_just doctor
  assert_failure
  assert_output --partial "auth.json mode"
}

@test "check passes with no destination at all" {
  assert_dir_not_exist "$PI_CODING_AGENT_DIR"

  run pi_just check
  assert_success
  assert_output --partial "no tracked secrets"
}

@test "check refuses a tracked secret" {
  printf '{"token":"secret"}' >"$PI_SRC/home/.pi/agent/auth.json"
  git -C "$PI_SRC" add -f home/.pi/agent/auth.json

  run pi_just check
  assert_failure
  assert_output --partial "tracked secret"
}

@test "check refuses a gitignore that stops covering a runtime path" {
  # The never-commit list and .gitignore are one rule in two files. doctor
  # reads the second to prove the first.
  grep -v '^/home/\.pi/agent/auth\.json$' "$PI_SRC/.gitignore" >"$PI_SRC/.gitignore.new"
  mv "$PI_SRC/.gitignore.new" "$PI_SRC/.gitignore"

  run pi_just check
  assert_failure
  assert_output --partial ".gitignore missing"
}

@test "status reports the source, the destination, and the pi binary" {
  run pi_just status
  assert_success
  assert_output --partial "source $PI_SRC"
  assert_output --partial "dest $PI_CODING_AGENT_DIR"
}
