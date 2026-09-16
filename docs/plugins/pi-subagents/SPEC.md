# pi-subagents landing

Verified against installed 0.68.0 on this host.

## Pin and tree

| Artifact | This repo | Live |
| --- | --- | --- |
| Pin | `settings.json` `packages` → `npm:pi-subagents` | symlink already |
| Install tree | no | `npm/node_modules/pi-subagents` |

## Sidecar

Live path when `PI_CODING_AGENT_DIR` is unset:
`$HOME/.pi/agent/extensions/subagent/config.json`.

Resolver (`src/extension/config.ts`): `getAgentDir()` then
`extensions/subagent/config.json`. Missing file loads `{}`. The
package writes the file only when `saveConfig` / `updateConfig`
runs. `just deploy` copies only top-level files under source
`extensions/`, so it does not create or clobber this nested path.

The file is policy, not secrets:

| Layer | Examples | Who writes |
| --- | --- | --- |
| Policy | `timeoutMs`, `fleetView`, `asyncByDefault`, spawn caps | operator or package |
| Live state | none in this file | — |

Settings-level keys (`subagents.defaultModel`, `agentScanDirs`,
`modelScope`, …) live in source `settings.json` if added. They are
not this sidecar.

Child sessions, run artifacts, and project schedules stay in the
live agent dir or in a project's `.pi/subagents/`. Never git here.

## Class

| Artifact | Class |
| --- | --- |
| `extensions/subagent/config.json` | live only until shared policy exists; do not symlink yet |
| `subagent-tool-description.md` | live only (optional custom tool prose) |
| child sessions / artifacts / schedules | live or project-local; never this git tree |

Do not symlink live `config.json` until this repo owns a policy
worth sharing across hosts. Do not copy it on every `just deploy`.

Create the live file only when changing defaults. After install,
`/reload` or start a new session.
