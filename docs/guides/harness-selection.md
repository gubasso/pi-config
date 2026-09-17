# Choosing a harness

Which agent binary this operator runs. Choosing a package inside that binary is [package-selection.md](./package-selection.md). Contract: [SPEC.md](../../SPEC.md) §1.

## Decision

Stay on upstream [Pi](https://pi.dev) plus the pins in `settings.json`. Recorded 2026-09-17, after a full comparison against [oh-my-pi](https://github.com/can1357/oh-my-pi), a Pi fork distributed as `omp`.

This is a harness decision, not a package decision. It binds until a revisit trigger below fires.

## What was compared

`omp` is a fork of Pi, not a Pi package. It ships its own binary, its own configuration directory at `~/.omp`, and 31 built-in tools. Its headline claims are 60 or more providers, 14 LSP operations, 28 debugger operations, and a Rust core near 80,000 lines.

The project is real and active. It carries 31,500 stars, 160 or more contributors, and roughly 24,000 commits across its first 8.5 months. Issue triage keeps pace: 3,730 issues closed, about 1,700 open, and only 84 of those open longer than 90 days. Release cadence runs to several versions per day.

Two claims drove the evaluation. The first is a token saving from hashline editing, where the model points at content-hash anchors instead of retyping lines. The published figure is 61 percent fewer output tokens on Grok 4 Fast, and roughly half that on Claude Opus. The second is a set of features assumed to need core access.

## Why the switch case failed

The switch case rested on one belief: that Pi's core tools cannot be replaced without forking the binary. Pi's own extension documentation contradicts it.

> Extensions can override built-in tools (`read`, `bash`, `powershell`, `edit`, `write`, `grep`, `find`, `ls`) by registering a tool with the same name.

Pi also exposes `tool_call` blocking, `tool_result` rewriting, `before_provider_request`, `after_provider_response`, non-destructive `context` message rewriting, and system-prompt injection at `before_agent_start`.

Because of that API, hashline already exists as installable Pi packages, and so does role-based model routing with provider fallback. The feature that justified the switch costs one `pi install` here, and `pi remove` reverts it. Virtual filesystem schemes, the advisor role, and persistent evaluation kernels are all reachable through the same hooks.

## What stays behind

Three things need the fork, and none of them motivated the evaluation.

| Feature                                     | Why no package reaches it                                            |
| ------------------------------------------- | -------------------------------------------------------------------- |
| In-process ripgrep, glob, and 58 coreutils  | Rust core. It buys call latency, not tokens                          |
| Stream rules that abort mid-token and retry | Pi exposes request and response hooks, not token-stream interception |
| Debugger integration across 28 operations   | Reachable in principle, but no mature Pi package exists today        |

## Why the fork loses on its own terms

Switching moves the critical path into a codebase this operator will not audit. `omp` rewrote `read`, `edit`, `grep`, and `bash`, and those have no fallback. An edit that lands on the wrong anchor writes wrong bytes, and the session continues. Roughly 90 commits per day, a large share of them machine-authored, is velocity rather than review.

A pinned package carries the same class of risk over a far smaller surface. The blast radius ends at `pi remove`. That difference, not the issue count and not the star count, decides it.

Cost of migration was not a criterion, consistent with [package-selection.md](./package-selection.md). The fork loses on effectiveness per unit of surface.

## What this decision does not claim

- It does not claim `omp` is a bad project. It is popular, maintained, and triaged.
- It does not claim the 61 percent figure is wrong. That figure is Grok 4 Fast output tokens, and this operator runs `xai/grok-4.6`, so it does not transfer as published.
- It does not reject any `omp` idea. Roles for child models, hash-anchored editing, and curated memory are all candidates for pins here.

## Revisit triggers

Reopen this decision when one of these happens.

- A hashline package lands here, and failed edits stay frequent anyway.
- Daily work turns into debugger work, which no Pi package answers today.
- Pi stops shipping releases, or removes the built-in tool override API.
- Upstream Pi adopts the remaining core features, which retires the comparison.
