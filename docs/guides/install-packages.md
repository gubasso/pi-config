# Install a Pi package

Operator procedure for third-party Pi packages on this machine.
The contract is [SPEC.md](../../SPEC.md). This page is the
manual.

Pi has no separate plugin type. A package is an npm or git unit
that ships extensions, skills, prompts, or themes. The pin lives
in this repo. The install tree does not.

## What belongs where

| Thing | Home |
| --- | --- |
| Pin (`npm:…`, `git:…`) | `settings.json` `packages` in this clone |
| Install tree | live `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/npm/` (or `git/`) |
| Plugin secrets / mixed sidecars | live agent dir unless `docs/plugins/<plugin-name>/SPEC.md` says otherwise |
| Plugin findings | `docs/plugins/<plugin-name>/` in this clone, not deployed |
| Plugin cache | live agent dir, never git |

`settings.json` is already a symlink from the live dir into this
clone. `pi install` writes the pin here. `just deploy` does not
run `pi install` and does not copy `npm/`.

Do not nest an `agent/` folder in this repo. Do not `pi install -l`
for a package you want everywhere. Do not vendor the package
source into this git tree.

## Review first

Packages run with full system access. Read the source before you
install a third-party unit.

```bash
npm view <name> repository
```

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

Confirm:

```bash
pi list
ls "${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/npm"
git -C /path/to/pi-config diff -- settings.json
```

Commit `settings.json` when the pin is a decision you want on
every host. Leave `npm/` untracked.

To try a package for one run without pinning:

```bash
pi -e npm:<name>
```

## Other hosts

1. Pull this repo.
2. `just deploy` (copies payloads, relinks `settings.json`).
3. Materialize trees. Global missing packages are **not** installed
   on Pi startup (that auto-install is project `.pi/` only).

```bash
pi update --extensions
```

If a pin is still missing:

```bash
pi install npm:<name>
```

Do not run bare `pi update`. That also tries to update the Pi
binary. Nix owns the binary (`PI_SKIP_VERSION_CHECK`).

## Remove

```bash
pi remove npm:<name>
```

That drops the pin from `settings.json` (this clone) and the live
tree. Commit the JSON change.

## Plugin config files

Classify the sidecar before you land it. The table lives in
[SPEC.md](../../SPEC.md) (Sidecar config files). Name the directory
and files as [docs/plugins/README.md](../plugins/README.md).

For `pi-web-access` see
[docs/plugins/pi-web-access/SPEC.md](../plugins/pi-web-access/SPEC.md):
no live `web-search.json` until you need keys or routing; then a
real `0600` file, not a symlink, not a deploy copy.

After install, `/reload` or start a new session. Packages do not
hot-reload on their own.

## Checks

```bash
just doctor
git check-ignore -q --no-index npm/foo web-search.json
```
