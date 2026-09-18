// Refuse a mutating `git worktree` from the agent's bash tool.
//
// Worktrunk owns where a worktree lands. `~/.config/worktrunk/config.toml` sets
// `worktree-path` at the top level with no per-project override, so every `wt`
// create derives `<repo>.ws/<repo>@<branch>` with each `/` flattened to `-`. A
// bare `git worktree add <path>` bypasses that template and leaves an
// off-convention seat that nothing downstream notices.
//
// The block is real, not advisory. Pi documents the `tool_call` event as "Fired
// before a tool executes. Can block", and `ToolCallEventResult` carries
// `{ block, reason }` (pi-coding-agent 0.85.1,
// `dist/core/extensions/types.d.ts:718` and `:818-827`). The reason string
// reaches the model as the tool result, so the refusal names the replacement
// instead of only failing.
//
// Scope, deliberately narrow:
//
//   - The bash tool only. `user_bash` fires for the operator's own `!` line and
//     its result type carries no `block`, so that path stays open by
//     construction. An operator who types the command has decided. This rule
//     binds the agent.
//   - The word `git` is the key, and it is load-bearing. Every other worktree
//     front end lands its own workflow and must pass untouched: `wt` is
//     Worktrunk itself, and `rk worktree add` is release-kit seating a branch
//     under its recorded checkout mode. Never widen the pattern to a bare
//     `worktree`, because that refuses the tools this rule exists to route work
//     into. `scripts/check-worktree-guard.mjs` holds those cases.
//   - Mutating subcommands only. `git worktree list` is how the layout gets
//     inspected and never trips.
//   - `git` and `worktree` must sit in the same simple command, so
//     `git status && echo "worktree add"` does not trip, and so
//     `git fetch origin && rk worktree add feat/x --apply` reaches `rk`.
//
// Known false positive: `git log --grep "worktree add"` trips, because `git`
// and the phrase share one command. The escape below covers it.
//
// Escape, per command and visible in the transcript:
//
//   PI_ALLOW_GIT_WORKTREE=1 git worktree repair /path
//
// Use it for `repair`, which Worktrunk does not wrap, and for a command that
// only quotes the phrase.

import type { ExtensionAPI, ToolCallEvent, ToolCallEventResult } from "@earendil-works/pi-coding-agent";

const MUTATING = /(?:^|[\s;&|(])git\b[^;&|\n]*?\bworktree\s+(?:add|move|remove|prune|repair|lock|unlock)\b/;
const ESCAPE = /(?:^|\s)PI_ALLOW_GIT_WORKTREE=1(?:\s|$)/;

const REASON = [
  "Blocked: this account creates worktrees through Worktrunk, never through bash `git worktree`.",
  "Use the `worktrunk` tool: `switch --create <branch>` opens a seat, `merge` lands it, `remove` retires it.",
  "Worktrunk owns the path, so the seat lands at `<repo>.ws/<repo>@<branch>` with every `/` flattened to `-`.",
  "`git worktree list` is read-only and is not blocked.",
  "For a deliberate one-off, prefix the command with `PI_ALLOW_GIT_WORKTREE=1`.",
].join(" ");

export default function(pi: ExtensionAPI): void {
  pi.on("tool_call", (event: ToolCallEvent): ToolCallEventResult | void => {
    if (event.toolName !== "bash") return;

    const command = event.input.command;
    if (typeof command !== "string") return;
    if (ESCAPE.test(command)) return;
    if (!MUTATING.test(command)) return;

    return { block: true, reason: REASON };
  });
}
