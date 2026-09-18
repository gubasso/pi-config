#!/usr/bin/env bash
# Run the suite for one cost budget across all three runners.
#
# This script is the mechanism. `.pre-commit-config.yaml` is the source of
# truth for when it runs: the `fast` budget at pre-commit, the `slow` budget
# at pre-push. `just test` calls pre-commit, never this file. Calling this
# file by hand is debugging.
#
# Three axes classify every test. This script selects on two of them and
# leaves the third to the path:
#
#   kind   unit / integration / e2e / meta   the directory under tests/
#   cost   fast / slow                       the argument to this script
#   venue  local / ci                        derived from $CI
#
# Each runner carries the same two tags in its own native form, so no runner
# learns a vocabulary invented here:
#
#   pytest  markers, selected with -m
#   bats    file tags, selected with --filter-tags
#   vitest  tests/helpers/tags.ts, reading the environment this script sets
#
# Every runner runs even when an earlier one fails, because a Python failure
# and a shell failure are usually unrelated and finding both in one pass is
# worth more than stopping early.

set -euo pipefail

usage() {
  echo "usage: scripts/run-tests.sh <fast|slow|all> [kind]" >&2
  echo "  kind is a directory under tests/, for debugging one slice" >&2
  exit 2
}

[ $# -ge 1 ] || usage

budget="$1"
kind="${2:-}"

case "$budget" in
fast) costs=(fast) ;;
slow) costs=(slow) ;;
all) costs=(fast slow) ;;
*) usage ;;
esac

# The venue a test must claim to run here. CI has no real pi binary, no
# landed destination, and no guarantee of network, so a test that needs this
# machine says `local` and CI skips it.
venue=local
if [ -n "${CI:-}" ]; then
  venue=ci
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$root"

scope="tests"
if [ -n "$kind" ]; then
  scope="tests/$kind"
  [ -d "$scope" ] || {
    echo "run-tests: no such kind: $scope" >&2
    exit 2
  }
fi

export PI_TEST_COST="${costs[*]}"
export PI_TEST_VENUE="$venue"

echo "== tests: cost=${costs[*]} venue=$venue scope=$scope"

failed=()
ran=0

# `**` needs globstar and still misses dotted directories, so ask find.
has_tests() {
  [ -n "$(find "$scope" -type f -name "$1" -print -quit 2>/dev/null)" ]
}

note_result() {
  local name="$1" status="$2"
  if [ "$status" -eq 0 ]; then
    echo "ok  $name"
  else
    echo "FAIL  $name" >&2
    failed+=("$name")
  fi
}

# --- Python -----------------------------------------------------------------
#
# -m takes a boolean marker expression. Cost is an OR across the budget and
# venue is a requirement, so a `slow` test never runs at pre-commit and a
# `ci`-only test never runs here.
cost_expr="$(
  IFS='|'
  echo "${costs[*]}"
)"
cost_expr="${cost_expr//|/ or }"

if has_tests "test_*.py"; then
  ran=$((ran + 1))
  set +e
  pytest "$scope" -m "($cost_expr) and $venue"
  status=$?
  set -e
  # 5 is "no tests collected", which a marker expression legitimately causes.
  [ "$status" -eq 5 ] && status=0
  note_result pytest "$status"
else
  echo "--  pytest: no test files under $scope"
fi

# --- Shell ------------------------------------------------------------------
#
# Multiple --filter-tags are an OR of the sets; a comma inside one is an AND.
# So one flag per cost, each requiring the venue.
if has_tests "*.bats"; then
  ran=$((ran + 1))
  filters=()
  for c in "${costs[@]}"; do
    filters+=(--filter-tags "$c,$venue")
  done
  set +e
  bats --recursive "${filters[@]}" "$scope"
  status=$?
  set -e
  note_result bats "$status"
else
  echo "--  bats: no test files under $scope"
fi

# --- TypeScript -------------------------------------------------------------
#
# vitest has no tag concept, so tests/helpers/tags.ts reads PI_TEST_COST and
# PI_TEST_VENUE and marks a test skipped. The same two words mean the same
# two things in all three runners.
if has_tests "*.test.ts"; then
  ran=$((ran + 1))
  set +e
  vitest run --root . "$scope"
  status=$?
  set -e
  note_result vitest "$status"
else
  echo "--  vitest: no test files under $scope"
fi

# --- Verdict ----------------------------------------------------------------

if [ "$ran" -eq 0 ]; then
  echo "run-tests: no test files at all under $scope" >&2
  exit 1
fi

if [ ${#failed[@]} -gt 0 ]; then
  echo "run-tests: ${#failed[@]} runner(s) failed: ${failed[*]}" >&2
  exit 1
fi

echo "ok  tests ${costs[*]} $venue"
