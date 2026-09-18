#!/usr/bin/env bats
# bats file_tags=slow,local,ci
#
# What `just deploy` lands, and what it refuses to land on.
#
# These are characterization tests. They describe the contract as it stands,
# and they are the reason the engine can move out of the justfile without
# anybody having to trust that the move was faithful. No test here may be
# edited to make a refactor pass.
#
# Tagged slow because each case runs a whole deploy against a throwaway home.

setup() {
  load "../helpers/common.bash"
  pi_setup
  pi_sandbox_repo >/dev/null
}

@test "deploy lands the payload and nothing outside home/" {
  run pi_just deploy
  assert_success

  assert_file_exist "$PI_CODING_AGENT_DIR/AGENTS.md"
  assert_file_exist "$PI_CODING_AGENT_DIR/prompts/review.md"
  assert_file_exist "$PI_CODING_AGENT_DIR/extensions/worktree-guard.ts"
  assert_symlink_to "$(pi_payload)/settings.json" "$PI_CODING_AGENT_DIR/settings.json"

  # The clone's own rules are machinery, and landing them would double the
  # agent's instructions.
  assert_file_not_exist "$PI_CODING_AGENT_DIR/SPEC.md"
  assert_file_not_exist "$PI_CODING_AGENT_DIR/justfile"
  run diff "$PI_SRC/AGENTS.md" "$PI_CODING_AGENT_DIR/AGENTS.md"
  assert_failure
}

@test "deploy copies the static payload rather than linking it" {
  run pi_just deploy
  assert_success

  # A copy, because the runtime does not write these and a link would make
  # the live directory depend on the clone staying put.
  assert_link_not_exist "$PI_CODING_AGENT_DIR/AGENTS.md"
  assert_link_not_exist "$PI_CODING_AGENT_DIR/prompts"
  assert_link_not_exist "$PI_CODING_AGENT_DIR/extensions"
  assert_files_equal "$(pi_payload)/AGENTS.md" "$PI_CODING_AGENT_DIR/AGENTS.md"
}

@test "deploy symlinks what the runtime writes, so writes reach git" {
  run pi_just deploy
  assert_success

  assert_symlink_to "$(pi_payload)/settings.json" "$PI_CODING_AGENT_DIR/settings.json"

  # The link is the whole point: Pi writes through it into the source tree.
  echo '{"theme":"written-by-the-runtime"}' >"$PI_CODING_AGENT_DIR/settings.json"
  run grep -q written-by-the-runtime "$(pi_payload)/settings.json"
  assert_success
}

@test "deploy writes a manifest of what it landed" {
  run pi_just deploy
  assert_success

  local manifest="$PI_CODING_AGENT_DIR/.pi-config-manifest.json"
  assert_file_exist "$manifest"

  run python3 -c "
import json, sys
paths = {e['path'] for e in json.load(open(sys.argv[1]))['paths']}
assert any(p.endswith('/AGENTS.md') for p in paths), 'AGENTS.md unrecorded'
assert any(p.endswith('/settings.json') for p in paths), 'settings.json unrecorded'
" "$manifest"
  assert_success
}

@test "a second deploy changes nothing" {
  run pi_just deploy
  assert_success
  local first
  first="$(find "$PI_CODING_AGENT_DIR" -printf '%P %y\n' | sort)"

  run pi_just deploy
  assert_success
  local second
  second="$(find "$PI_CODING_AGENT_DIR" -printf '%P %y\n' | sort)"

  assert_equal "$first" "$second"
}

@test "deploy refuses a destination Home Manager still owns" {
  mkdir -p "$PI_CODING_AGENT_DIR"
  ln -s /nix/store/does-not-exist-agents-md "$PI_CODING_AGENT_DIR/AGENTS.md"

  run pi_just deploy
  assert_failure
  assert_output --partial "Home Manager still owns"
}

@test "deploy refuses a landing root that is itself a symlink" {
  # Both halves of the containment check move with the root, so a swapped
  # ~/.pi would redirect every landing and every deletion.
  mkdir -p "$BATS_TEST_TMPDIR/elsewhere"
  ln -s "$BATS_TEST_TMPDIR/elsewhere" "$HOME/.pi"

  run pi_just deploy
  assert_failure
}

@test "deploy converges install trees through pi remove" {
  run pi_just deploy
  assert_success

  # The stub records every call. Convergence must go through `pi remove`,
  # because deleting a tree by hand leaves the dependency in Pi's own
  # package.json and the next install resurrects it.
  assert_file_exist "$PI_STUB_LOG"
}
