# Testing

How to run the suite, and how to add to it. Contract: [SPEC.md](../../SPEC.md) §16. Module layout: [SPEC.md](../../SPEC.md) §15.

## Running

```sh
just test        # what a commit must pass
just test-slow   # what a push must pass
just test-all    # both
```

All three call pre-commit, because the hook is the source of truth for when the suite runs. A recipe that ran the tests directly would be a second answer to that question.

While you write one test, call the runner or the tool by hand:

```sh
scripts/run-tests.sh fast unit     # one budget, one kind
pytest tests/unit -k veto          # one case
bats tests/e2e/converge.bats       # one file
vitest run tests/unit              # the TypeScript half
```

That is debugging. The gate is `git commit`.

## The three axes

Every test carries three things. Two of them you write; the third comes from where the file lives.

| Axis  | Values                               | Where it comes from          |
| ----- | ------------------------------------ | ---------------------------- |
| kind  | `unit`, `integration`, `e2e`, `meta` | the directory under `tests/` |
| cost  | `fast`, `slow`                       | you write it                 |
| venue | `local`, `ci`                        | you write it                 |

Pick the kind by what the test drives:

- `unit` is one function, with no filesystem beyond `tmp_path`.
- `integration` is several modules together, with real files under `tmp_path`.
- `e2e` is the command line a person types.
- `meta` is an invariant of this source tree rather than of the payload.

Pick the cost by where it belongs. `fast` runs on every commit, so keep it under a second. `slow` runs on every push.

Pick the venue by what the test needs. `local` means this machine: the real `pi` binary, the network, or a landed destination. `ci` means it runs anywhere the devShell runs. Most tests carry both.

A test that names neither a cost nor a venue never runs. Collection refuses it rather than letting it pass silently.

## Adding a Python test

Put it in `tests/unit/test_<module>.py`, matching the module under `scripts/pi_config/`. A meta test requires one test module per engine module.

```python
import pytest

import pi_config

pytestmark = [pytest.mark.fast, pytest.mark.local, pytest.mark.ci]


def test_a_runtime_owned_name_is_vetoed(tmp_home) -> None:
    dest = tmp_home / ".pi" / "agent"
    dest.mkdir(parents=True)
    roots = pi_config.landing_roots(str(dest))

    assert pi_config.runtime_owned(str(dest / "auth.json"), roots)
```

Take `tmp_home` whenever the code under test touches a path. It gives a throwaway `$HOME` with `PI_CODING_AGENT_DIR` inside it, and it refuses to run if that lands anywhere under the real home.

## Adding a shell test

Put it in `tests/e2e/<recipe>.bats`. Tag the whole file on the second line.

```bash
#!/usr/bin/env bats
# bats file_tags=slow,local,ci

setup() {
  load "../helpers/common.bash"
  pi_setup
  pi_sandbox_repo >/dev/null
}

@test "deploy lands the payload" {
  run pi_just deploy
  assert_success
  assert_file_exist "$PI_CODING_AGENT_DIR/AGENTS.md"
}
```

`pi_setup` is not optional. It builds the throwaway home, puts a stub `pi` on PATH, and detaches from the repository git handed the hook.

`pi_sandbox_repo` makes a throwaway copy of this tree with its own history. Use it whenever a test changes the payload, which must never happen in the tree you are working in.

## Adding a TypeScript test

Put it in `tests/unit/<name>.test.ts`. vitest has no tag concept, so the cost and venue come from a helper.

```ts
import { expect, test } from "vitest";

import { tagged } from "../helpers/tags.ts";

test("blocks a mutating git worktree", tagged("fast", ["local", "ci"]), () => {
  expect(verdict("git worktree add ../x")).toBe("block");
});
```

The extension under test is loaded as source. Node strips the types and `tsconfig.json` sets `erasableSyntaxOnly`, so what the test drives is what `just deploy` copies.

## What a test may never do

Write to the real `$HOME`. Write to the live agent directory. Write into this repository's own `home/` payload, which an autouse fixture checks after every test.

Run `git` without dropping the environment a hook inherits. A pre-commit hook runs inside `git commit`, which exports `GIT_INDEX_FILE` and `GIT_DIR`. A `git add` in a sandbox would write the real index instead, replace the operator's staged state, and report nothing. `tmp_home` and `pi_setup` both drop it.

## Adding a dependency

Python and shell tools come from `flake.nix`. Add the package, re-enter the shell, and add the command to the loop in `just devshell-check`; a meta test keeps those two in step.

JavaScript comes from `package-lock.json`, which Nix builds:

```sh
npm add -D <package> --package-lock-only
direnv reload
```

The `--package-lock-only` is set by default in `.npmrc`. A plain `npm install` would write into a `node_modules` that Nix owns.
