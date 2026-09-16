# pi-queue-steer landing

Verified against upstream `1f67c4c83e364538f347fdc8c2005c38eaaf8536` (tag `v0.2.0`): `index.ts`, `queued-input.ts`, `queue-state.ts`, `editor-render.ts`, `package.json`, README.

## Pin and tree

| Artifact     | This repo                                                                                                      | Live                                     |
| ------------ | -------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| Pin          | `settings.json` `packages` → `git:github.com/tmustier/pi-queue-steer@1f67c4c83e364538f347fdc8c2005c38eaaf8536` | symlink already                          |
| Install tree | no                                                                                                             | `git/github.com/tmustier/pi-queue-steer` |

`package.json` declares one entry point, `index.ts`, under the `pi.extensions` key. The package ships no skill, prompt, or theme.

## Sidecars

None. The package creates no file under the live agent dir and no file under `$HOME/.pi`.

The only file read in the source is the source file of a queued command, in `queued-input.ts`. When a queued row expands a prompt template or an Agent Skill, the package reads that resource from the path Pi already reported for it. Those resources are Pi's own prompts and skills, which this clone deploys. They are not sidecars of this package.

The package also reads two keys of Pi's own settings through `SettingsManager`: `steeringMode` and `followUpMode` (`index.ts:268`). It never writes them. `settings.json` is the source file in this clone and is already a symlink from the live dir, so no new row is needed.

Queue state, pause state, and edit drafts stay in memory for the session. They never reach the transcript or the session store.

## Source review

Read before install, as `docs/guides/install-packages.md` requires:

- No network call. No `fetch`, no download, no telemetry.
- No subprocess. No `child_process`, no `exec`, no `spawn`.
- No write to disk. The single `node:fs` import is `readFileSync`.
- No environment variable read.
- Runtime dependencies are the three Pi peer packages, which Pi supplies.

## Class

Empty `sidecars` array. Checked; nothing to land.

## Interaction with the other pins

The package registers no tool name, so it collides with no pin in `settings.json`. It wraps the active Pi editor instead of replacing Pi's input model, and upstream states that it composes with custom editors.

After install, `/reload` or start a new session.
