# narumitw-pi-plan-mode landing

Verified against published 0.58.0 (requires Pi 0.80.6 or newer) and upstream settings reference <https://github.com/narumiruna/pi-extensions/blob/main/packages/pi-plan-mode/docs/settings.md>.

## Pin and tree

| Artifact     | This repo                                                 | Live                                      |
| ------------ | --------------------------------------------------------- | ----------------------------------------- |
| Pin          | `settings.json` `packages` → `npm:@narumitw/pi-plan-mode` | symlink already                           |
| Install tree | no                                                        | `npm/node_modules/@narumitw/pi-plan-mode` |

## Sidecars

Live path when `PI_CODING_AGENT_DIR` is unset: `$HOME/.pi/agent/pi-plan-mode.json`.

Resolver (`src/settings.ts`): `getAgentDir()` then `pi-plan-mode.json`. Missing file uses defaults (inherit thinking, automatic safe built-ins, `clear-on-start`, same-as-plan fresh runtime, `PLAN.md`, no shortcut). The package writes the file on an explicit Settings save (`updatePlanModeSettings` / `publishSettings`). Reads use `O_NOFOLLOW` and require a regular file; saves `rename` a temp file onto the path. A symlink is ignored (`settings path is not a regular file`) and a save would replace the link. A valid legacy `plan-mode.json` in the same directory remains readable and is never auto-migrated; a later save creates the canonical file and leaves the legacy file untouched.

The canonical file is policy, not secrets:

| Layer          | Examples                                                                                                                                    | Who writes          |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| Policy         | `thinkingLevel`, `defaultPlanTools`, `implementationPlanRetention`, `defaultImplementationModel`, `defaultPlanExportPath`, `toggleShortcut` | operator or package |
| Trust override | `safeSubcommands` (JSON-only; bypasses limited-shell checks)                                                                                | operator            |
| Live state     | none in this file                                                                                                                           | —                   |

`safeSubcommands` is a trust override, not an API token. It stays in this tracked file if we ever set it.

Plan workflow state (ready / saved / active plan) lives in the session, not this sidecar. Exported Markdown (`PLAN.md` by default) is a project-cwd file, not an agent-dir sidecar.

## Class

| Artifact            | Class                                       | Why                                              |
| ------------------- | ------------------------------------------- | ------------------------------------------------ |
| `pi-plan-mode.json` | `copy` (`followsSymlinks: false`, hardlink) | No secrets; TUI writes; package refuses symlinks |
| `plan-mode.json`    | `live-only`                                 | Legacy name we refuse to create                  |

Source `pi-plan-mode.json` holds explicit defaults (`thinkingLevel` inherit, `clear-on-start`, `PLAN.md`). Deploy hardlinks dest to source. `/plan settings` atomically replaces dest and breaks the hardlink; the next `just deploy` imports dest into source when only dest changed vs HEAD, then restores the hardlink. After install, `/reload` or start a new session.
