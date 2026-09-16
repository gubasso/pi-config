# pi-worktrunk landing

Verified against published 0.9.2 (`worktrunk.ts`, `package.json`, README), which is upstream commit `c63b6415a6cd14b591c04ac3b1a6f658796abd7b`.

## Pin and tree

| Artifact     | This repo                                       | Live                            |
| ------------ | ----------------------------------------------- | ------------------------------- |
| Pin          | `settings.json` `packages` → `npm:pi-worktrunk` | symlink already                 |
| Install tree | no                                              | `npm/node_modules/pi-worktrunk` |

`package.json` declares one entry point, `worktrunk.ts`, under the `pi.extensions` key. The package ships no skill, prompt, or theme.

## External requirement

The package runs the `wt` binary and does not bundle it. Nix owns `wt` on this host: `~/.local/state/nix/profile/bin/wt`, version 0.74.0. The source requires the `WORKTRUNK_DIRECTIVE_CD_FILE` protocol and `wt list --format=json` schema 2, which Worktrunk 0.70 and later provide. Without `wt` on `PATH`, `/wt` reports a missing-binary message and nothing else breaks.

Session movement needs TUI or RPC mode. In print or JSON mode, a directory request stops continuation and reports where to restart Pi.

## Sidecars

None. The package creates no file under the live agent dir and no file under `$HOME/.pi`.

Three write paths exist in the source, and none of them is a sidecar of this package:

| Write                                                        | Where                         | Owner                         |
| ------------------------------------------------------------ | ----------------------------- | ----------------------------- |
| Directive reply file, `mode 0o600` (`worktrunk.ts:40`)       | fresh `mkdtemp` dir in tmpdir | removed in `finally` at `:99` |
| Session snapshot before a fork (`worktrunk.ts:214`)          | Pi's own session store        | Pi                            |
| Branch marker, through `wt config state marker set` (`:189`) | Worktrunk's own state store   | `wt`                          |

Worktrunk configuration reaches the package only through `wt config show --format=json` (`worktrunk.ts:292`), which parses the alias list. The package never writes that configuration, and this clone does not land it. The package reads no key of Pi's `settings.json`.

## Source review

Read before install, as `docs/guides/install-packages.md` requires:

- No network call. No `fetch`, no download, no telemetry.
- Subprocess: yes, and that is the point. It spawns `wt` and `git rev-parse`. Arguments pass as an argv array with no shell, so no shell expansion happens.
- Environment: it reads none by name. It passes the inherited environment to the `wt` child and adds `WORKTRUNK_DIRECTIVE_CD_FILE`, `WORKTRUNK_SHELL_CWD`, and `PWD`.
- Disk writes: the three rows above only.
- Runtime dependencies are the three Pi peer packages plus `typebox`, all supplied by Pi.

Upstream declares every peer dependency as `*`, so a future Pi release can break the package while the pin stays the same.

## Class

Empty `sidecars` array. Checked; nothing to land.

## Interaction with the other pins

The package registers the slash command `wt` (`worktrunk.ts:1012`) and the tool `worktrunk` (`:1089`). No other pin in `settings.json` uses either name, and no installed tree mentions Worktrunk.

Model calls run Worktrunk commands without a further Pi confirmation. Worktrunk keeps its own hook, approval, dirty-worktree, and force-flag checks, so approvals still come from `wt config approvals`.

After install, `/reload` or start a new session.
