#!/usr/bin/env bats
# bats file_tags=slow,local,ci
#
# What `just deploy` removes, and what it refuses to remove.
#
# This is the file that matters. The engine here deletes files in a directory
# that also holds auth.json, session transcripts, and installed package trees.
# The commit messages for that work recorded their proof in prose. These tests
# are that proof, repeatable.
#
# Characterization: no test here may be edited to make a refactor pass.

setup() {
  load "../helpers/common.bash"
  pi_setup
  pi_sandbox_repo >/dev/null
}

manifest() {
  echo "$PI_CODING_AGENT_DIR/.pi-config-manifest.json"
}

# Add a path to the manifest as though a previous deploy had landed it.
forge_manifest_entry() {
  python3 - "$(manifest)" "$1" "${2:-copy}" <<'PY'
import json, sys
path, target, how = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path) as handle:
    doc = json.load(handle)
doc["paths"].append({"path": target, "how": how})
with open(path, "w") as handle:
    json.dump(doc, handle, indent=2)
PY
}

# A prompt doctor does not require, so a test can stop declaring it.
#
# review.md cannot serve here: doctor lists it as a required payload file and
# deploy ends by calling doctor, so removing it fails the run before prune is
# ever reached. That guard has its own test below.
declare_extra_prompt() {
  echo "# extra" >"$PI_SRC/home/.pi/agent/prompts/extra.md"
}

@test "a prompt the repo stops declaring is removed from the destination" {
  declare_extra_prompt
  run pi_just deploy
  assert_success
  assert_file_exist "$PI_CODING_AGENT_DIR/prompts/extra.md"

  rm "$PI_SRC/home/.pi/agent/prompts/extra.md"
  run pi_just deploy
  assert_success

  # This is the whole point of converging: the repo is the state of the live
  # directory, not a floor under it.
  assert_file_not_exist "$PI_CODING_AGENT_DIR/prompts/extra.md"
}

@test "deploy-report names what it would remove and removes nothing" {
  declare_extra_prompt
  run pi_just deploy
  assert_success
  rm "$PI_SRC/home/.pi/agent/prompts/extra.md"

  run pi_just deploy-report
  assert_success
  assert_output --partial "extra.md"
  assert_file_exist "$PI_CODING_AGENT_DIR/prompts/extra.md"
}

@test "deploy refuses a source tree missing a required payload file" {
  rm "$PI_SRC/home/.pi/agent/prompts/review.md"

  run pi_just deploy
  assert_failure
  assert_output --partial "missing"
}

@test "a file predating the manifest is reported, not deleted" {
  run pi_just deploy
  assert_success

  # Deploy never landed this, so prune cannot see it in the manifest.
  echo stale >"$PI_CODING_AGENT_DIR/prompts/leftover.md"

  run pi_just deploy
  assert_success
  assert_file_exist "$PI_CODING_AGENT_DIR/prompts/leftover.md"
  assert_output --partial "unmanaged"
}

@test "deploy-adopt removes what a plain deploy only reports" {
  run pi_just deploy
  assert_success
  echo stale >"$PI_CODING_AGENT_DIR/prompts/leftover.md"

  run pi_just deploy-adopt
  assert_success
  assert_file_not_exist "$PI_CODING_AGENT_DIR/prompts/leftover.md"
}

@test "a manifest naming auth.json fails the run and keeps the credential" {
  run pi_just deploy
  assert_success

  printf '{"token":"secret"}' >"$PI_CODING_AGENT_DIR/auth.json"
  chmod 600 "$PI_CODING_AGENT_DIR/auth.json"
  forge_manifest_entry "$PI_CODING_AGENT_DIR/auth.json"

  # The manifest is trusted state, not proof. Behind it sits a hard veto, so
  # a corrupted or hand-edited manifest fails rather than destroying a
  # credential.
  run pi_just deploy
  assert_failure
  assert_file_exist "$PI_CODING_AGENT_DIR/auth.json"
}

@test "a manifest naming a session transcript fails the run" {
  run pi_just deploy
  assert_success

  mkdir -p "$PI_CODING_AGENT_DIR/sessions"
  echo '{}' >"$PI_CODING_AGENT_DIR/sessions/a.jsonl"
  forge_manifest_entry "$PI_CODING_AGENT_DIR/sessions/a.jsonl"

  run pi_just deploy
  assert_failure
  assert_file_exist "$PI_CODING_AGENT_DIR/sessions/a.jsonl"
}

@test "the veto covers a whole runtime-owned directory, not just a basename" {
  run pi_just deploy
  assert_success

  mkdir -p "$PI_CODING_AGENT_DIR/npm/node_modules/pi-thing"
  echo '{}' >"$PI_CODING_AGENT_DIR/npm/node_modules/pi-thing/package.json"
  forge_manifest_entry "$PI_CODING_AGENT_DIR/npm/node_modules/pi-thing/package.json"

  run pi_just deploy
  assert_failure
  assert_file_exist "$PI_CODING_AGENT_DIR/npm/node_modules/pi-thing/package.json"
}

@test "a manifest naming a path outside the landing roots fails the run" {
  run pi_just deploy
  assert_success

  echo keep >"$BATS_TEST_TMPDIR/outside.txt"
  forge_manifest_entry "$BATS_TEST_TMPDIR/outside.txt"

  # Landing roots are policy derived in code, never fields read back from
  # the manifest, so a manifest cannot widen what deploy may delete.
  run pi_just deploy
  assert_failure
  assert_file_exist "$BATS_TEST_TMPDIR/outside.txt"
}

@test "prune leaves a runtime file sharing a directory with a landed one" {
  echo "# extra" >"$PI_SRC/home/.pi/agent/prompts/extra.md"
  run pi_just deploy
  assert_success
  assert_file_exist "$PI_CODING_AGENT_DIR/prompts/extra.md"

  # A package writes this at run time. Prune removes recorded entries with
  # os.remove and os.rmdir, never a recursive delete, so a directory holding
  # both deploy's file and somebody else's survives by construction.
  echo runtime >"$PI_CODING_AGENT_DIR/prompts/.runtime-note"
  rm "$PI_SRC/home/.pi/agent/prompts/extra.md"

  run pi_just deploy
  assert_success
  assert_file_not_exist "$PI_CODING_AGENT_DIR/prompts/extra.md"
  assert_dir_exist "$PI_CODING_AGENT_DIR/prompts"
  assert_file_exist "$PI_CODING_AGENT_DIR/prompts/review.md"
  assert_file_exist "$PI_CODING_AGENT_DIR/prompts/.runtime-note"
}
