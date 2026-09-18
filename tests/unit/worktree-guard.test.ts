// Prove what home/.pi/agent/extensions/worktree-guard.ts refuses and what it
// lets through.
//
// The guard keys on the word `git`. That is the whole reason every other
// worktree front end survives it, and it is the property most likely to be
// lost by a later edit that widens the pattern to a bare `worktree`. The allow
// rows below are the regression cover for exactly that edit.
//
// The extension is loaded as source. Node strips its types and tsconfig sets
// erasableSyntaxOnly, so what runs here is what `just deploy` copies.

import { expect, test } from "vitest";
import type {
  ExtensionAPI,
  ToolCallEvent,
  ToolCallEventResult,
} from "@earendil-works/pi-coding-agent";

import guard from "../../home/.pi/agent/extensions/worktree-guard.ts";
import { tagged } from "../helpers/tags.ts";

type Handler = (event: ToolCallEvent) => ToolCallEventResult | void;

/** Register the extension against a fake host and return its tool_call hook. */
function toolCallHandler(): Handler {
  let handler: Handler | undefined;

  const host = {
    on(event: string, fn: Handler) {
      if (event === "tool_call") handler = fn;
    },
  };

  guard(host as unknown as ExtensionAPI);

  if (!handler) {
    throw new Error("worktree-guard registered no tool_call handler");
  }
  return handler;
}

function verdict(toolName: string, command: string): "block" | "allow" {
  const event = {
    type: "tool_call",
    toolCallId: "test",
    toolName,
    input: { command },
  } as unknown as ToolCallEvent;

  return toolCallHandler()(event)?.block === true ? "block" : "allow";
}

const cases: Array<["block" | "allow", string, string, string]> = [
  // Bare git worktree mutation: the one thing this guard exists to refuse.
  ["block", "bash", "git worktree add ../foo branch", "add"],
  ["block", "bash", "cd /repo && git worktree add ../x", "add after cd"],
  ["block", "bash", "git -C /repo worktree add ../x", "add with -C"],
  ["block", "bash", "git worktree move ../a ../b", "move"],
  ["block", "bash", "git worktree remove ../x", "remove"],
  ["block", "bash", "git worktree prune", "prune"],

  // Other worktree front ends land their own workflow and stay open.
  ["allow", "bash", "wt switch --create feat/x", "wt switch"],
  ["allow", "bash", "wt merge feat/x", "wt merge"],
  ["allow", "bash", "wt remove feat/x -D", "wt remove"],
  ["allow", "bash", "rk worktree add feat/x --apply", "rk add"],
  ["allow", "bash", "rk worktree list", "rk list"],
  ["allow", "bash", "rk worktree prune", "rk prune"],
  [
    "allow",
    "bash",
    "cd /home/me/release-kit.ws/release-kit && rk worktree add feat/x --apply",
    "rk add after cd",
  ],
  [
    "allow",
    "bash",
    "git fetch origin && rk worktree add feat/x --apply",
    "rk add after a git command",
  ],

  // Read-only inspection stays open.
  ["allow", "bash", "git worktree list", "git list"],
  ["allow", "bash", "git worktree list --porcelain", "git list porcelain"],

  // Quoting the phrase is not invoking it.
  ["allow", "bash", 'git status && echo "worktree add"', "echoing the phrase"],
  ["allow", "bash", 'grep -rn "worktree add" docs/', "grepping the phrase"],

  // The per-command escape.
  ["allow", "bash", "PI_ALLOW_GIT_WORKTREE=1 git worktree repair /p", "the escape"],

  // Other tools carry no bash command to inspect.
  ["allow", "read", "git worktree add ../foo", "a non-bash tool"],
];

// A plain loop rather than test.for, because every test here carries its cost
// and venue and the table helper has nowhere to put them.
for (const [want, toolName, command, label] of cases) {
  test(`${want}: ${label}`, tagged("fast", ["local", "ci"]), () => {
    expect(verdict(toolName, command)).toBe(want);
  });
}

test("the refusal names the replacement", tagged("fast", ["local", "ci"]), () => {
  const event = {
    type: "tool_call",
    toolCallId: "test",
    toolName: "bash",
    input: { command: "git worktree add ../x" },
  } as unknown as ToolCallEvent;

  const result = toolCallHandler()(event);

  // A refusal that only fails teaches the model nothing. The reason string
  // reaches it as the tool result.
  expect(result?.reason).toContain("worktrunk");
  expect(result?.reason).toContain("PI_ALLOW_GIT_WORKTREE");
});
