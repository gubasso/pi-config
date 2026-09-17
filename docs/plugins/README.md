# Plugin docs

One directory per third-party Pi package this operator installs. Humans and coding agents read it before changing the pin, a sidecar file, or deploy.

Repo contract: [SPEC.md](../../SPEC.md). Selection: [guides/package-selection.md](../guides/package-selection.md). Pin form: [guides/package-pinning.md](../guides/package-pinning.md). Install steps: [guides/install-packages.md](../guides/install-packages.md). LSP: [guides/lsp.md](../guides/lsp.md).

These directories record **how** a chosen pin is landed. They do not decide which package wins. Fit to an existing sidecar class is not a selection criterion.

## Directory name

`docs/plugins/<plugin-name>/`

`<plugin-name>` is the package id with the source prefix stripped:

| Pin in `settings.json`        | Directory       |
| ----------------------------- | --------------- |
| `npm:pi-web-access`           | `pi-web-access` |
| `npm:@scope/pkg@1.2.3`        | `scope-pkg`     |
| `git:github.com/user/repo@v1` | `repo`          |

Rules: lowercase kebab-case. Drop `npm:` and `git:`. Drop `@version` and git refs. For a scoped npm name, drop `@` and turn `/` into `-`. Do not use the live path, the npm folder, or a slogan as the name.

## Files inside each directory

Keep it flat. Three required documents, optional extras as sibling `.md` files, no nested package folders.

| File            | Required | What it is                                          |
| --------------- | -------- | --------------------------------------------------- |
| `README.md`     | yes      | Index: pin, upstream, one-line landing, links       |
| `SPEC.md`       | yes      | Binding landing: each sidecar, class, why           |
| `sidecars.json` | yes      | Machine contract `just deploy` / `just doctor` read |
| `<topic>.md`    | no       | Extra research that is not the landing contract     |

`README.md` does not repeat the SPEC. `SPEC.md` does not narrate install (that is the guide). Do not put secrets or `npm/` trees here. These paths are not deployed.

## The audited version

Pins are unversioned, so the plugin `SPEC.md` is where this repo records which upstream code the operator actually read. Open every `SPEC.md` with that line:

```markdown
Verified against upstream `<40-char-sha>` (`file-a.ts`, `file-b.ts`, README).
```

Use the published version instead of a SHA when the package comes from npm, as `pi-better-edit` does. Name the files that were read, not only the commit.

Bump that line in a commit after `pi update --extensions` moves the tree and the operator reads the upstream diff. That commit is what replaces the old habit of bumping a SHA inside the pin. Steps: [guides/package-pinning.md](../guides/package-pinning.md).

`sidecars.json` lists every config file the package reads that this clone must classify, including leftover names we refuse to create. Schema:

```json
{
  "sidecars": [
    {
      "path": "relative/to-clone.json",
      "root": "agent | pi-home",
      "class": "live-only | symlink | copy",
      "sensitive": false,
      "runtimeWrites": true,
      "required": true,
      "followsSymlinks": true
    }
  ]
}
```

`path` is relative to this clone. No `..`. `root` defaults to `agent` (dest is the live agent dir). `pi-home` dest is `$HOME/.pi/<path>`. `sensitive: true` requires `class: live-only`. `runtimeWrites: true` requires `class: symlink`, unless `followsSymlinks` is false, in which case `class` must be `copy` and deploy lands a hardlink (3-way sync against HEAD). `required` defaults to true for `copy` / `symlink` and is always false for `live-only`. Optional `copy` / `symlink` rows may omit the source file until we author one.

An empty `sidecars` array means the package was checked and has no config files this clone lands.

## Current packages

Do not list pins here. Source of truth is `settings.json` `packages`. Each pin has a directory named by the rules above. `just check` proves the pairing and sidecar classes. `just status` reports whether the live tree and each sidecar dest exist.
