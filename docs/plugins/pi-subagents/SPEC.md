# pi-subagents landing

Verified against installed 0.68.0 and upstream <https://github.com/nicobailon/pi-subagents/blob/main/docs/configuration.md>.

## Pin and tree

| Artifact     | This repo                                       | Live                            |
| ------------ | ----------------------------------------------- | ------------------------------- |
| Pin          | `settings.json` `packages` → `npm:pi-subagents` | symlink already                 |
| Install tree | no                                              | `npm/node_modules/pi-subagents` |

## Sidecars

Live path when `PI_CODING_AGENT_DIR` is unset: `$HOME/.pi/agent/extensions/subagent/config.json`.

Resolver (`src/extension/config.ts`): `getAgentDir()` then `extensions/subagent/config.json`. Missing file loads `{}`. The package writes the file when `saveConfig` / `updateConfig` runs.

The file is policy, not secrets:

| Layer      | Examples                                               | Who writes          |
| ---------- | ------------------------------------------------------ | ------------------- |
| Policy     | `timeoutMs`, `fleetView`, `asyncByDefault`, spawn caps | operator or package |
| Live state | none in this file                                      | —                   |

Settings-level keys (`subagents.defaultModel`, `agentScanDirs`, `modelScope`, …) live in source `settings.json` if added. They are not this sidecar.

Optional custom tool prose: `subagent-tool-description.md` at the agent-dir root (project config dir first, then `~/.pi/agent/subagent-tool-description.md`). The package does not write it.

Child sessions, run artifacts, and project schedules stay in the live agent dir or in a project's `.pi/subagents/`. Never git here.

## Class

| Artifact                          | Class                | Why                                                  |
| --------------------------------- | -------------------- | ---------------------------------------------------- |
| `extensions/subagent/config.json` | `symlink`            | No secrets; runtime may write                        |
| `subagent-tool-description.md`    | `copy`, not required | No secrets; we own the bytes; runtime does not write |

Source `extensions/subagent/config.json` is `{}` until this operator sets policy. Do not author `subagent-tool-description.md` until custom tool prose is wanted. After install, `/reload` or start a new session.
