# LSP / semantic code intelligence

Selection policy: [package-selection.md](./package-selection.md). Landing procedure: [install-packages.md](./install-packages.md).

The job is to give the model deterministic semantic tools so it does not infer symbol relationships from `rg`. Definitions, references, diagnostics, symbols, and semantic rename. Tight edit → small diagnostic feedback. Bounded results.

Repository checks (`just check`, typecheck, lint, tests) stay authoritative. LSP does not replace them.

## Ranking (effectiveness first)

| Rank | Package                                                                                   | Why it sits here                                                                                                                                                     |
| ---- | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | [code-yeongyu/pi-lsp-client](https://github.com/code-yeongyu/pi-lsp-client)               | Right primitives, agentic lifecycle, post-edit diagnostics, bounded lists (200), no junk tools                                                                       |
| 2    | [samfoy/pi-lsp-extension](https://github.com/samfoy/pi-lsp-extension)                     | Same job plus hover and a well-capped auto-diag (errors, 10 lines, no lazy start). Loses on tool bloat: completions, AST rewrite, Brazil extras, system-prompt nudge |
| 3    | [pi-lsp-adapter](https://github.com/nikmmd/pi-lsp-adapter)                                | Best pagination (`lsp_more`). Incomplete job: no rename, no code actions. 0.1.3                                                                                      |
| 4    | [@gitawego/pi-lsp](https://github.com/gitawego/pi-lsp)                                    | OpenCode-style persistent clients, rich queries, result caps. 11 tools, 0.1.0, auto-download                                                                         |
| 5    | [@narumitw/pi-lsp](https://github.com/narumiruna/pi-extensions/tree/main/packages/pi-lsp) | Wrong job: diagnostics + `lsp_fix` only, spawn-per-call, unbounded diagnostic text. Highest adoption. Do not pin it for this job                                     |
| —    | `lsp-pi`, unscoped `pi-lsp`, `jtepe/pi-lsp`, `@signalridge/pi-lsp`, `pi-lsp-bridge`       | Kitchen-sink, stale, fork, or placeholder                                                                                                                            |

Do not install two of these. They all register `lsp_diagnostics` and most register `/lsp`.

### Why rank 1 is pi-lsp-client

Verified against the upstream README and source (2026-09-16):

- Tools the model actually needs: `lsp_diagnostics`, `lsp_goto_definition`, `lsp_find_references`, `lsp_symbols`, `lsp_prepare_rename`, `lsp_rename`. Six tools. No completions.
- Persistent pool with refcount, 5-minute idle reap, 60s init timeout, abort-aware acquire, one retry on read tools, no retry on rename, `session_shutdown` cleanup. Built for agent turns, not for bolting an IDE onto Pi.
- Post-edit hook appends LSP errors after `write` / `edit` / `apply_patch` so the model can fix in the same turn.
- Result caps in `src/lsp/constants.ts`: 200 references, 200 symbols, 200 diagnostics, 50 files per directory query.
- Rename is a real workspace apply (`executionMode: "sequential"`). That is more deterministic than `rg` plus a pile of `edit`s. Prepare-rename is a separate tool, so the model can fail closed.

Gaps to live with, not reasons to rank it down:

- Not on npm (`@code-yeongyu/pi-lsp-client` 404, and the unscoped name is absent too). No git tags and no releases, so the pin follows the default branch. Read the diff before you trust an update: [package-pinning.md](./package-pinning.md).
- User config is `~/.pi/lsp-client.json` (and project `.pi/lsp-client.json`), not under the live agent dir. The `home/` mirror holds it at `home/.pi/lsp-client.json`. Do not reject the pin.
- `/lsp install` can download servers. Do not use it. Put language servers on PATH. Never treat auto-install as required.
- No hover tool. Hover is nice; definition/references/diagnostics/rename are the job.
- Post-edit text is not hard-capped at 10 lines (samfoy is). The diagnostics tool still truncates at 200.

### Why not samfoy first

It is the most capable single package. Completions are dead weight in an LLM prompt. `code_search` / `code_rewrite` / `code_overview` are a second job. Tree-sitter fallback can look like type intelligence when no server is running. Brazil/lombok/`/bemol` do not help this operator. Last push 2026-06-10.

If structural search is wanted, pin [code-yeongyu/pi-ast-grep](https://github.com/code-yeongyu/pi-ast-grep) as its own package (`ast_grep_search`, `ast_grep_replace` dry-run default). That is the composition senpi already uses. Do not take samfoy just to get AST bundled with LSP.

`npm:pi-ast-grep` is a different package by a different author, published once as 0.1.0 with no repository field. Pin the git source. Never shorten it to the npm name.

### Why not narumitw for this job

Same vendor as `pi-plan-mode`, 0.49.7, ~10k downloads/month, PATH-only, two tools. Excellent as a diagnostics helper. It does not expose definition, references, or rename. Spawn-per-call throws away incremental document state. Diagnostics are returned in full with no size bound. Compatibility with plan-mode is not a reason to pin the wrong LSP.

`pi-plan-mode` stays. It does a different job.

### Compatibility with current pins

`pi-web-access`, `pi-subagents`, `pi-plan-mode`, `pi-intercom`, `@99percentpeople/pi-todo` do not register LSP tools. No collision. Child subagent sessions inherit global extensions; that is useful (semantic tools in workers) and is not a conflict.

## Setup in this clone

Landed. Pins, plugin docs, and `home/.pi/lsp-client.json` are in this clone. Trees are live `git/` after `pi update --extensions`. Do not skip classify on a version bump. The audited commit lives in `docs/plugins/pi-lsp-client/SPEC.md`, not in the pin.

1. One-shot, no pin:

   ```bash
   pi -e git:github.com/code-yeongyu/pi-lsp-client
   ```

   In that session: `/lsp status`. Call `lsp_diagnostics` on a real file whose server is on PATH. Confirm the six tools exist.

2. Read the loaded source. List every config path it reads (`~/.pi/lsp-client.json`, `.pi/lsp-client.json`, anything under the live agent dir). Classify each. If a path is outside the live agent dir, add it to `sidecars.json` at its `$HOME`-relative path so this clone stays SoT. Do not vendor the repo into `home/.pi/agent/extensions/`.

3. Pin the unversioned source:

   ```bash
   pi install git:github.com/code-yeongyu/pi-lsp-client
   ```

   That writes `settings.json` in this clone. Record the commit you read in step 2 as the `Verified against upstream` line of the plugin SPEC.

4. Author `docs/plugins/pi-lsp-client/{README.md,SPEC.md,sidecars.json}` and the source sidecar. A managed default that disables nothing required is fine. Do not enable `/lsp install` recipes as the way servers appear.

5. Language servers stay on PATH (Home Manager / Nix). Typical: `typescript-language-server`, `pyright` or `basedpyright`, `ruff`, `rust-analyzer`, `gopls`, `nixd`. The extension probes PATH. Missing defaults should fail closed with an install hint, not a download.

6. `just deploy && just doctor`. `/reload` or a new session. Confirm with `/lsp` that the pool is empty until the first tool call (lazy spawn).

7. Do **not** also pin `@narumitw/pi-lsp`, `pi-lsp-extension`, `pi-lsp-adapter`, or `@gitawego/pi-lsp`.

Optional second pin, later, only if structural search is the next job: `git:github.com/code-yeongyu/pi-ast-grep` with `PI_OFFLINE=1` if auto-download of `sg` is unwanted.

## Recheck

Re-open this ranking if pi-lsp-client publishes a tagged npm package, grows a 10-line post-edit cap, or adds hover without adding junk tools. Re-open it if samfoy drops completions and AST from the default tool set. Do not re-open it because deploy would have to learn a new config path.
