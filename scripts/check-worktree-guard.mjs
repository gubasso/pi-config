// Prove what home/.pi/agent/extensions/worktree-guard.ts refuses and what it
// lets through. Run by `just check`; not deployed.
//
// The guard keys on the word `git`. That is the whole reason every other
// worktree front end survives it, and it is the property most likely to be
// lost by a later edit that widens the pattern to a bare `worktree`. The allow
// rows below are the regression cover for exactly that edit.
//
// Loaded through Node's native TypeScript type stripping, so the extension
// needs no build step here. Its only import is `import type`, which erases.

import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const extension = resolve(root, "home/.pi/agent/extensions/worktree-guard.ts");

const cases = [
  // Bare git worktree mutation: the one thing this guard exists to refuse.
  ["block", "bash", "git worktree add ../foo branch"],
  ["block", "bash", "cd /repo && git worktree add ../x"],
  ["block", "bash", "git -C /repo worktree add ../x"],
  ["block", "bash", "git worktree move ../a ../b"],
  ["block", "bash", "git worktree remove ../x"],
  ["block", "bash", "git worktree prune"],

  // Other worktree front ends land their own workflow and stay open.
  ["allow", "bash", "wt switch --create feat/x"],
  ["allow", "bash", "wt merge feat/x"],
  ["allow", "bash", "wt remove feat/x -D"],
  ["allow", "bash", "rk worktree add feat/x --apply"],
  ["allow", "bash", "rk worktree list"],
  ["allow", "bash", "rk worktree prune"],
  ["allow", "bash", "cd /home/me/release-kit.ws/release-kit && rk worktree add feat/x --apply"],
  ["allow", "bash", "git fetch origin && rk worktree add feat/x --apply"],

  // Read-only inspection stays open.
  ["allow", "bash", "git worktree list"],
  ["allow", "bash", "git worktree list --porcelain"],

  // Quoting the phrase is not invoking it.
  ["allow", "bash", 'git status && echo "worktree add"'],
  ["allow", "bash", 'grep -rn "worktree add" docs/'],

  // The per-command escape.
  ["allow", "bash", "PI_ALLOW_GIT_WORKTREE=1 git worktree repair /p"],

  // Other tools carry no bash command to inspect.
  ["allow", "read", "git worktree add ../foo"],
];

const module = await import(extension);
let handler;
module.default({
  on: (event, fn) => {
    if (event === "tool_call") handler = fn;
  },
});
if (!handler) {
  console.error("worktree-guard: no tool_call handler registered");
  process.exit(1);
}

let failed = 0;
for (const [want, toolName, command] of cases) {
  const result = handler({ type: "tool_call", toolCallId: "check", toolName, input: { command } });
  const got = result?.block === true ? "block" : "allow";
  if (got !== want) {
    failed += 1;
    console.error(`worktree-guard: want ${want}, got ${got}: ${command}`);
  }
}

if (failed > 0) {
  console.error(`worktree-guard: ${failed} of ${cases.length} cases wrong`);
  process.exit(1);
}
console.log(`ok  worktree guard ${cases.length} cases`);
