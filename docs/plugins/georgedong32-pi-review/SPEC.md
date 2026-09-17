# georgedong32-pi-review landing

Verified against published 0.8.5 (`src/config.ts`, `src/types.ts`, `package.json`, README). Requires `pi-subagents` >= 0.41 (this clone pins `npm:pi-subagents`) and Pi >= 0.74.

## Pin and tree

| Artifact     | This repo                                                  | Live                                       |
| ------------ | ---------------------------------------------------------- | ------------------------------------------ |
| Pin          | `settings.json` `packages` → `npm:@georgedong32/pi-review` | symlink already                            |
| Install tree | no                                                         | `npm/node_modules/@georgedong32/pi-review` |

Do not also pin unscoped `npm:pi-review`. Both register `/review` and both use `pi-review.json`.

## Sidecars

Live path is hardcoded to `$HOME/.pi/agent/pi-review.json` (`src/config.ts` `DEFAULT_CONFIG_PATH`). The package does not honor `PI_CODING_AGENT_DIR`. This operator's live agent dir is that path.

A missing file is valid: `loadRawConfig` returns `{}` and `mergeWithDefaults` applies package defaults, including gate model `anthropic/claude-haiku-4-5`. Source `home/.pi/agent/pi-review.json` overrides that: gate and bundled reviewers use `xai/grok-4.6` at thinking `low`. `conventions` stays disabled. Routing stays `adaptive`.

`/review-config` and `writeConfig` write the file: temp path then `renameSync` onto `pi-review.json`. A symlink is replaced. Deploy therefore hardlinks dest to source (`followsSymlinks: false`). The next `just deploy` 3-way-syncs if dest drifted.

The file is policy, not secrets:

| Layer      | Examples                                       | Who writes          |
| ---------- | ---------------------------------------------- | ------------------- |
| Policy     | `gate.model`, `gate.thinking`, reviewer models | operator or package |
| Live state | none in this file                              | —                   |

Run artifacts (`.pi/pi-review/runs/` in a project cwd, tmpdir `pi-review-ws-*`) are cache. Never git here.

## Class

| Artifact                   | Class                                       | Why                                                        |
| -------------------------- | ------------------------------------------- | ---------------------------------------------------------- |
| `.pi/agent/pi-review.json` | `copy` (`followsSymlinks: false`, hardlink) | No secrets; atomic rename; package would replace a symlink |

After install, `/reload` or start a new session. Local review: `/review` or `/review --lite`. GitHub PR numbers need `gh`; this host already has it.
