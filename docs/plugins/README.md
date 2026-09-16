# Plugin docs

One directory per third-party Pi package this operator installs.
Humans and coding agents read it before changing the pin, a
sidecar file, or deploy.

Repo contract: [SPEC.md](../../SPEC.md).
Install steps: [guides/install-packages.md](../guides/install-packages.md).

## Directory name

`docs/plugins/<plugin-name>/`

`<plugin-name>` is the package id with the source prefix stripped:

| Pin in `settings.json` | Directory |
| --- | --- |
| `npm:pi-web-access` | `pi-web-access` |
| `npm:@scope/pkg@1.2.3` | `scope-pkg` |
| `git:github.com/user/repo@v1` | `repo` |

Rules: lowercase kebab-case. Drop `npm:` and `git:`. Drop `@version`
and git refs. For a scoped npm name, drop `@` and turn `/` into `-`.
Do not use the live path, the npm folder, or a slogan as the name.

## Files inside each directory

Keep it flat. Two required documents, optional extras as sibling
`.md` files, no nested package folders.

| File | Required | What it is |
| --- | --- | --- |
| `README.md` | yes | Index: pin, upstream, one-line landing, links |
| `SPEC.md` | yes | Binding landing: sidecar class, copy / symlink / live-only |
| `<topic>.md` | no | Extra research that is not the landing contract |

`README.md` does not repeat the SPEC. `SPEC.md` does not narrate
install (that is the guide). Do not put secrets, `npm/` trees, or
live `web-search.json` here. These paths are not deployed.

## Current packages

| Directory | Pin |
| --- | --- |
| [pi-web-access](./pi-web-access/README.md) | `npm:pi-web-access` |
