# pi-better-edit landing

Verified against published 1.7.0 (`index.ts`, `src/hash-store.ts`, `src/constants.ts`, README) and upstream <https://github.com/Rianico/pi-better-edit>.

## Pin and tree

| Artifact     | This repo                                                       | Live                              |
| ------------ | --------------------------------------------------------------- | --------------------------------- |
| Pin          | `settings.json` `packages` → `npm:pi-better-edit` (unversioned) | symlink already                   |
| Install tree | no                                                              | `npm/node_modules/pi-better-edit` |

## Why this pin

Row 11 of the omp feature checklist. The package that won under [package-selection.md](../../guides/package-selection.md): content-hash anchors, same `read`/`edit` names, fail-closed stale/unserved ranges, session-keyed served state, stock `grep` left alone. `pi-hashline-edit` lost (repo 404, 2-char neighbor hashes, 3-way merge). `pi-hashline-edit-pro` lost (replaces `edit` with `replace`/`insert`, default grep override, silent auto-fix).

## Sidecars

None. The package reads no file under the live agent dir and no file under `$HOME/.pi`. README: "No config."

Runtime store (`src/hash-store.ts`):

| Path                                                                                                    | Role                                 |
| ------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| `$XDG_CONFIG_HOME/pi-better-edit/hash-store.sqlite` (else `~/.config/pi-better-edit/hash-store.sqlite`) | served hashes, undo bytes, snapshots |
| same dir, `hash-store.json` then `hash-store.json.bak`                                                  | one-shot import from older versions  |
| `-wal` / `-shm` next to the sqlite file                                                                 | SQLite sidecars, not this clone's    |

The sqlite file holds file contents for undo. It is a cache, not operator policy. This clone does not land it. `sidecars.json` cannot name `$XDG_CONFIG_HOME`; do not extend deploy to copy undo bytes into git. Reset: quit Pi, delete the sqlite file and its `-wal`/`-shm`, next session rebuilds.

Do not share or bind-mount this directory across the host and project containers. Each runtime with its own `HOME` or `XDG_CONFIG_HOME` gets its own store. That is correct. Served rows are keyed `(session_id, absolute path)` and rebuild on the next `read`. Undo is one row per absolute path and holds file bytes; two writers on one sqlite file (especially over a volume) is corruption, not sync. A resumed session without this store fail-closes and reject-and-serves fresh anchors.

The package does not read Pi `settings.json` keys.

## Tools

`index.ts` registers `read`, `read_skill`, `edit`, `undo_last_edit`, and a `write` hook that refreshes served hashes after a stock `write`. Built-in `grep` stays.

No other pin in `settings.json` registers `read`, `edit`, `read_skill`, or `undo_last_edit`. Do not install a second hashline package beside this one.

## Class

Empty `sidecars` array. Checked; nothing to land.

After install, `/reload` or start a new session. This session still has stock `read`/`edit` until then.
