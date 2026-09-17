# 99percentpeople-pi-todo landing

Verified against published 1.2.7 (npm `@99percentpeople/pi-todo`) and upstream <https://github.com/99percentpeople/pi-extensions/blob/master/extensions/todo/README.md>, plus bundled `@99percentpeople/pi-shared-settings` 0.1.3 (`packages/shared-settings/index.ts`).

## Pin and tree

| Artifact     | This repo                                                   | Live                                        |
| ------------ | ----------------------------------------------------------- | ------------------------------------------- |
| Pin          | `settings.json` `packages` → `npm:@99percentpeople/pi-todo` | symlink already                             |
| Install tree | no                                                          | `npm/node_modules/@99percentpeople/pi-todo` |

The GitHub tree is the source of that npm package. Do not pin `git:github.com/99percentpeople/pi-extensions`; the monorepo root is not a Pi package and would not isolate this extension.

## Sidecars

Live path when `PI_CODING_AGENT_DIR` is unset: `$HOME/.pi/agent/99extensions.json`.

Resolver (`config.ts` → `getSharedSettingsPath()`): `getAgentDir()` then `99extensions.json`. Missing file, empty object, or a missing `todo` key uses defaults (`collapsedTaskLimit` 3, `showDependencyNumbers` true, `reminderInterval` 3). The package writes the file on an explicit `/99settings` change (`saveTodoConfig` → `writeSettingsNamespace`). Reads use `readFileSync` (follows a symlink). Saves write `${path}.${pid}.tmp` then `renameSync` onto the path, which replaces a symlink with a regular file.

The file is a namespaced store for every installed `@99percentpeople` extension. This pin is the only one that lists it. `just check` forbids the same sidecar path on two pins, so later packages from that org add a namespace here and do not re-declare the path.

The `todo` object is policy, not secrets:

| Layer      | Examples                                                          | Who writes          |
| ---------- | ----------------------------------------------------------------- | ------------------- |
| Policy     | `collapsedTaskLimit`, `showDependencyNumbers`, `reminderInterval` | operator or package |
| Live state | none in this file                                                 | —                   |

Todo plan state (keys, statuses, revisions) lives in the session (`todo` tool-result details and hidden custom messages). It is not an agent-dir sidecar.

SSH passwords used by other packages in this family, if ever installed, live in a separate secrets file, not here.

## Class

| Artifact                      | Class                                       | Why                                              |
| ----------------------------- | ------------------------------------------- | ------------------------------------------------ |
| `.pi/agent/99extensions.json` | `copy` (`followsSymlinks: false`, hardlink) | No secrets; TUI writes; package refuses symlinks |

Source `home/.pi/agent/99extensions.json` holds explicit `todo` defaults. Deploy hardlinks dest to source. `/99settings` atomically replaces dest and breaks the hardlink; the next `just deploy` imports dest into source when only dest changed vs HEAD, then restores the hardlink. After install, `/reload` or start a new session.
