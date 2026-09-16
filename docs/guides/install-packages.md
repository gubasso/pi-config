# Install a Pi package

Operator procedure for third-party Pi packages on this machine. The contract is [SPEC.md](../../SPEC.md). This page is the manual.

Pi has no separate plugin type. A package is an npm or git unit that ships extensions, skills, prompts, or themes. The pin lives in this repo. The install tree does not. Every plugin config file is classified and landed from this repo.

## What belongs where

| Thing                       | Home                                                            |
| --------------------------- | --------------------------------------------------------------- |
| Pin (`npm:…`, `git:…`)      | `settings.json` `packages` in this clone                        |
| Install tree                | live `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/npm/` (or `git/`) |
| `copy` / `symlink` sidecars | this clone, same relative path as live; deploy lands them       |
| `live-only` sidecars        | live agent dir only; gitignored; this clone stays blind         |
| Plugin findings             | `docs/plugins/<plugin-name>/` in this clone, not deployed       |
| Plugin cache                | live agent dir, never git                                       |

`settings.json` is already a symlink from the live dir into this clone. `pi install` writes the pin here. `just deploy` does not run `pi install` and does not copy `npm/`. It does land classified sidecars.

Do not nest an `agent/` folder in this repo. Do not `pi install -l` for a package you want everywhere. Do not vendor the package source into this git tree.

## Review first

Packages run with full system access. Read the source before you install a third-party unit.

```bash
npm view <name> repository
```

Then read upstream docs and list every config file the package reads under the live agent dir. Classify each one before `pi
install` writes the pin.

## Classify

| Class                             | When                                                    | Land                                                                                   |
| --------------------------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `live-only`                       | Can hold tokens, or a leftover name we refuse to create | gitignore; no source file; deploy does not touch dest                                  |
| `symlink`                         | No secrets; runtime may write                           | track here; deploy symlinks                                                            |
| `copy`                            | No secrets; we own the bytes; runtime does not write    | track here; deploy copies                                                              |
| `copy` + `followsSymlinks: false` | Runtime writes, but the package refuses symlinks        | track here; deploy hardlinks; TUI atomic save breaks the link; next deploy 3-way-syncs |

Sensitive wins. Mixed files that can hold keys stay `live-only`.

Write `docs/plugins/<plugin-name>/README.md`, `SPEC.md`, and `sidecars.json`. Create the source file for every required `copy` / `symlink` row. `{}` is a managed default.

## Install (this host)

From any directory, after `just deploy` has linked `settings.json`:

```bash
pi install npm:<name>
```

Examples:

```bash
pi install npm:pi-web-access
pi install npm:@scope/pkg@1.2.3
pi install git:github.com/user/repo@v1
```

Pi then:

1. Writes the spec into live `settings.json`, which is this clone.
2. Installs the tree under live `npm/` or `git/`.

Then land sidecars:

```bash
just deploy
just doctor
```

Confirm:

```bash
pi list
ls "${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/npm"
git -C /path/to/pi-config diff -- settings.json
```

Commit `settings.json` and the plugin docs when the pin is a decision you want on every host. Leave `npm/` untracked.

To try a package for one run without pinning:

```bash
pi -e npm:<name>
```

## Other hosts

1. Pull this repo.
2. `just deploy` (copies payloads, relinks settings and sidecars).
3. Materialize trees. Global missing packages are **not** installed on Pi startup (that auto-install is project `.pi/` only).

```bash
pi update --extensions
```

If a pin is still missing:

```bash
pi install npm:<name>
```

Do not run bare `pi update`. That also tries to update the Pi binary. Nix owns the binary (`PI_SKIP_VERSION_CHECK`).

Create live-only secret files on that host if needed. Do not copy them from another machine unless you intend to.

## Remove

```bash
pi remove npm:<name>
```

That drops the pin from `settings.json` (this clone) and the live tree. Delete `docs/plugins/<plugin-name>/` and any source sidecars that existed only for that pin. Commit the JSON and docs change.

## Checks

```bash
just doctor
just status
just check
```
