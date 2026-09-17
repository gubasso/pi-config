# pi-config specification

Personal source of truth for [Pi Coding Agent](https://pi.dev). This repository is the **source** of global config. It is not the live agent directory. `just deploy` copies static payloads Pi only reads, and symlinks the files Pi mutates that this repo still tracks.

This document is the contract for the repo: layout, tracking rules, Nix boundary, secrets, deploy, and when a piece of this tree must become its own package.

---

## 1. Purpose

`pi-config` is the git-backed source of one operator's global Pi config (cloned per machine, deployed onto that machine).

It is **not**:

- the Pi CLI itself (`@earendil-works/pi-coding-agent`)
- the live agent directory Pi reads at runtime
- a Home Manager module that writes store-backed `settings.json`
- a catalog of third-party add-ons
- a place to store credentials or session transcripts

It **is**:

- the source of `settings.json`, `keybindings.json`, `AGENTS.md`, prompts, skills, local extensions, themes, optional subagent defs
- the source of every non-secret plugin sidecar this operator installs
- the git history of those config decisions
- the justfile that lands those files where Pi reads them

Pi mutates `settings.json`, `keybindings.json`, and classified plugin sidecars through live symlinks into this clone. Static payloads are copies; Pi does not write them. Secret sidecars stay in the live dir only.

---

## 2. Naming

| Layer                             | Name                                                      |
| --------------------------------- | --------------------------------------------------------- |
| GitHub repository                 | `pi-config`                                               |
| Local clone                       | anywhere in the src tree                                  |
| Live agent directory              | `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`                 |
| `package.json` `"name"` (private) | `pi-config`                                               |
| Published subset, if any          | `@<you>/pi-config` or a **different** `pi-<feature>` repo |
| Extracted shareable add-on        | `pi-<feature>` (see §9)                                   |

Do not name this repo `pi-coding-agent`, `pi-agent`, `pi-plugins`, `pi-packages`, or `.pi`.

- `pi-coding-agent` is the upstream CLI package.
- `pi-<feature>` is the convention for a single installable package.
- `.pi` matches the on-disk prefix `~/.pi/` but is a bad GitHub name.
- `pi-plugins` / `pi-packages` name the add-on mechanism, not this source repository.

`pi-agent-config` is a name used when a repo is marketed primarily as `pi install git:…`. This repo is the operator's source tree and deploy, not a public package. Keep `pi-config`.

---

## 3. Where Pi reads config

Pi 0.85.1 loads global config from one directory:

```text
${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}
```

The default is `$HOME/.pi/agent`. That is a home-dot path, not XDG. This project does not set `PI_CODING_AGENT_DIR` and does not set `PI_CODING_AGENT_SESSION_DIR`. Nix does not set them either.

`just deploy` writes owned files into that same resolved path, so the binary needs no extra wiring. If the operator has already exported `PI_CODING_AGENT_DIR`, deploy follows it. If they have not, deploy uses `$HOME/.pi/agent`.

Do not clone this repository onto `~/.pi/agent`. Do not export `PI_CODING_AGENT_DIR` pointing at this clone, and that includes `home/.pi/agent` inside it. The mirror makes that last one look correct. It is not, and `just doctor` fails on it. All three moves turn the clone into the live directory, which is not this design.

Auth follows the live agent directory:

```text
${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/auth.json
```

There is no separate auth directory. Sessions, `npm/`, `git/`, `bin/`, `trust.json`, and `models-store.json` live there too, next to the deployed files, and never in this git tree.

---

## 4. Division of responsibility

| Concern                                                            | Source of truth                                                                              |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| Pi binary, PATH, extra tools (`nodejs`, `bun`, `git`, …)           | Home Manager / Nix                                                                           |
| `PI_SKIP_VERSION_CHECK`                                            | Home Manager (store install cannot self-update)                                              |
| Live agent directory path                                          | Pi's default, unless the operator already overrode it                                        |
| API keys, OAuth                                                    | `/login` → live `auth.json`; sops/agenix/1Password/env; never Nix store; never this git tree |
| Authored config (`AGENTS.md`, prompts, skills, extensions, themes) | **this repository**, copied by `just deploy`                                                 |
| `settings.json`, `keybindings.json`                                | **this repository**; live path is a symlink, so `/settings` and `pi install` write here      |
| Session JSONL                                                      | live agent dir `sessions/` (untracked)                                                       |
| `npm/`, `git/`, `bin/` install trees                               | live agent dir; declared via source `settings.json` `packages`                               |
| Plugin sidecar files                                               | **this repository** classifies and lands every one; see §9                                   |

Home Manager must not write the agent directory. One writer per file: `just deploy` copies static payloads and creates the symlinks; Pi writes through those symlinks; Nix owns the binary.

---

## 5. Repository layout

The repo root holds machinery. The payload lives under `home/`, which is a literal mirror of `$HOME`, so a payload's repo path states its own destination. Stock names still apply inside the mirror, so deploy is a copy or a symlink of that path. The repo root is **not** `PI_CODING_AGENT_DIR`, and neither is `home/.pi/agent`.

```text
pi-config/                          # source tree (clone lives anywhere)
├── SPEC.md                         # this document
├── README.md
├── AGENTS.md                       # clone-only rules; NOT deployed
├── .gitignore
├── justfile                        # deploy / doctor / status / check
├── scripts/package-pins.py         # derive pins; not deployed
├── package.json                    # private; optional pi manifest
├── tsconfig.json                   # for local TypeScript extensions
├── flake.nix                       # devShell: every tool a recipe or hook calls
├── flake.lock
├── .envrc                          # direnv enters that devShell
├── .pre-commit-config.yaml         # the gates; see §14
├── dprint.json                     # formatter of record for markdown and JSON
├── .markdownlint-cli2.jsonc
├── .editorconfig
├── committed.toml                  # commit message content rules
├── ruff.toml
├── lychee.toml
│
├── docs/
│   ├── guides/                     # operator manuals; not deployed
│   └── plugins/<plugin-name>/      # README + SPEC + sidecars.json; not deployed
│
└── home/                           # mirrors $HOME
    └── .pi/
        ├── lsp-client.json         # plugin sidecar; dest $HOME/.pi/lsp-client.json
        └── agent/                  # dest ${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}
            ├── settings.json       # tracked; live path is a symlink
            ├── keybindings.json    # tracked; live path is a symlink
            ├── pi-plan-mode.json   # plugin sidecar; hardlink at dest
            ├── pi-review.json      # plugin sidecar; hardlink at dest
            ├── 99extensions.json   # plugin sidecar; hardlink at dest
            ├── models.example.json # committed template
            ├── AGENTS.md           # payload; deployed as global context
            ├── APPEND_SYSTEM.md    # optional; deployed if present
            ├── intercom/config.json
            ├── prompts/            # deployed; slash prompts → /name
            │   └── <name>.md
            ├── skills/             # deployed if present
            │   └── <name>/
            │       └── SKILL.md
            ├── extensions/         # deployed if present
            │   └── <name>.ts
            ├── themes/             # deployed if present
            │   └── <name>.json
            └── agents/             # deployed if present
                └── <name>.md
```

`just deploy` lands `home/.pi/agent/` into `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`, and the rest of `home/` into `$HOME`:

- copy: `AGENTS.md`, `prompts/`, and each of `extensions/`, `themes/`, `skills/`, `agents/`, `APPEND_SYSTEM.md` that exists, plus every plugin sidecar classified `copy`
- symlink: `settings.json`, `keybindings.json` (when the source file exists), plus every plugin sidecar classified `symlink`. Pi's `writeFileSync` follows the link.
- never: anything outside `home/`. That is the whole rule. It covers the root `AGENTS.md`, `SPEC.md`, `README.md`, `justfile`, `scripts/`, `package.json`, `.gitignore`, `.git/`, and `docs/`. Inside `home/` it also excludes `auth.json`, `trust.json`, `models.json`, `models-store.json`, live-only plugin sidecars, `sessions/`, `npm/`, `git/`, and `bin/`, none of which this tree tracks.

Pi will still create these in the **live** agent directory, never in the mirror:

```text
auth.json
models.json
web-search.json
web-search-cache/
sessions/
npm/
git/
bin/
trust.json
mcp-cache.json
models-store.json
*.log
```

Do not invent alternate folder names (`lib/skills`, `plugins/`) inside `home/.pi/agent/` unless those paths are listed in `settings.json`. Stock names are the convention so deploy is a copy or a symlink of those paths.

---

## 6. Tracking policy

### Commit (this git tree)

Edit source files in this clone, then `just deploy`. That is the path a change takes to a host.

Every payload path below is relative to `home/`, so `.pi/agent/settings.json` is tracked at `home/.pi/agent/settings.json`.

| Path                                                                                                  | Why                                             |
| ----------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| `.pi/agent/settings.json`                                                                             | Defaults, theme, compaction, `packages` list    |
| `.pi/agent/keybindings.json`                                                                          | Bindings you set                                |
| classified plugin sidecars (`copy` / `symlink`)                                                       | Declared in `docs/plugins/<name>/sidecars.json` |
| `.pi/agent/AGENTS.md`, `.pi/agent/APPEND_SYSTEM.md`                                                   | Behavior contract (payload)                     |
| `.pi/agent/prompts/`, `skills/`, `extensions/`, `themes/`, `agents/`                                  | Resources                                       |
| `.pi/agent/models.example.json`                                                                       | Template without secrets                        |
| root `AGENTS.md`                                                                                      | Clone-only rules while cwd is this repo         |
| `package.json`, `tsconfig.json`, `flake.nix`, `SPEC.md`, `README.md`, `.gitignore`, `justfile` (root) | Repo tooling                                    |
| `docs/guides/`, `docs/plugins/`                                                                       | Operator manuals and per-package landing notes  |

Grey field inside `settings.json`: `lastChangelogVersion`. Pi bumps it through the symlink, so the working tree goes dirty. Commit the bump with the upgrade or restore that one field. Do not untrack the file because of it.

A file Pi creates in the live agent directory is not in this git tree. The mirror under `home/` holds only what this repo authors. Symlinked files come back: `/settings`, `pi install`, and plugin Settings saves that write a `symlink` sidecar. Commit when the write was a config decision. `/login` and live-only sidecars are never committed.

### Never commit

| Path                                           | Why                                                                                              |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `auth.json`                                    | API keys and OAuth refresh tokens. Mode `0600`. `/login` writes the live file.                   |
| `web-search.json`                              | Third-party package secrets and curator state (pi-web-access). Live agent dir only. Mode `0600`. |
| other `live-only` plugin sidecars              | Declared in `docs/plugins/<name>/sidecars.json`. Same rule as `auth.json`.                       |
| `web-search-cache/`                            | pi-web-access fetch cache. Live agent dir only.                                                  |
| `.env`, `.env.*`                               | Same class of secret. Keep `.env.example` if needed.                                             |
| `sessions/`                                    | Transcripts; leak code and secrets. They belong in the live agent dir.                           |
| `npm/`, `git/`, `bin/`                         | Install trees in the live agent dir. The declaration is `packages` in source `settings.json`.    |
| `node_modules/`                                | Tooling / extension deps.                                                                        |
| `*.log`, `mcp-cache.json`, `models-store.json` | Runtime cache.                                                                                   |
| `trust.json`                                   | Machine-local project trust.                                                                     |

### `models.json`

If it contains API keys, machine URLs, or gateway hostnames:

- commit `models.example.json` with placeholders
- copy once per machine to untracked live `models.json`

If it is only public model ids with no secrets, commit `models.json` here and deploy it like other authored files.

---

## 7. Secrets

Credential resolution (highest first), as Pi documents it:

1. `--api-key`
2. live agent dir `auth.json`
3. environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, …)
4. `apiKey` on a custom provider in live `models.json`

`auth.json` wins over env vars. Do not be surprised when a stale live file overrides a new sops-injected variable.

Allowed patterns:

- live `auth.json` created by `/login` or by hand (`0600`)
- Home Manager / sops / agenix exporting provider env vars
- `auth.json` `key` set to an **environment variable name** or a `!command` (1Password, `pass`, …), never a literal secret in git

Forbidden:

- keys in `settings.json` or committed `models.json`
- keys in Home Manager option values that land in the Nix store
- committing `auth.json` “just this once”
- deploying `auth.json` from this clone (the clone must not have it)

Work vs personal: two live agent dirs (or `pi-profiles`-style wrappers), not one shared `auth.json`.

---

## 8. `package.json` in this repo

This file is **repo tooling**, not “publish my home directory.”

```json
{
  "name": "pi-config",
  "private": true,
  "keywords": ["pi-package"],
  "pi": {
    "extensions": ["./home/.pi/agent/extensions"],
    "skills": ["./home/.pi/agent/skills"],
    "prompts": ["./home/.pi/agent/prompts"],
    "themes": ["./home/.pi/agent/themes"]
  }
}
```

The real file carries only `prompts`. Add a key when its directory exists.

The paths point into the `home/` mirror, because that is where the resources live in this tree. A nested path under a dot directory is valid, and the reason is exact: `package-manager.js` treats an entry as a glob only when it contains `*` or `?`. Every other entry resolves with `resolve(root, entry)` and then walks that directory. Upstream states the rule at `package-manager.js:137`: "Glob entries discover visible paths; exact entries can target dot paths or symlinked trees."

**Never write a glob into this manifest.** `expandPackageGlob` drops any match whose path has a segment starting with `.`, so a pattern under `home/.pi/` matches nothing and fails silently. Keep every entry exact.

Pi auto-loads those folders from the **live** agent dir after deploy. The manifest exists so that:

- a subset _could_ be installed elsewhere later
- `pi install .` records this clone as a package while developing

`pi -e <path>` loads one extension file. It does not read this manifest, so it is not a test of these paths. Neither `pi install` nor `pi list` validates a manifest path either: both accept a directory that does not exist. The resolution above is read from the installed Pi 0.85.1 source. A session that lists `/review` from the manifest is still unproven, and it is not needed, because `just deploy` is what lands the prompts.

Do not treat `pi install git:github.com/<you>/pi-config` as the primary distribution path. That command loads resources from conventional dirs; it does **not** cleanly install your `settings.json`, `AGENTS.md`, or secrets — and it _will_ expose whatever you failed to exclude. Host landing is `just deploy`.

`.gitignore` minimum: the never-commit list in §6, plus `models-store.json`.

---

## 9. Packages vs this repo

Pi has no separate “plugin” type. Shareable units are **packages**: extensions, skills, prompt templates, themes. Others install them with `pi install` into the live agent dir. Operator steps: [docs/guides/install-packages.md](./docs/guides/install-packages.md). Per-package findings: [docs/plugins/](./docs/plugins/README.md).

### Choosing a package

Pick the package that makes the model more precise, deterministic, and effective at the job. Token-sane results (bounded output, no junk tools, no prompt dump) are part of that job. Popularity, maturity, and compatibility with the rest of the stack are clues. They are not a veto. Operator manuals: [docs/guides/package-selection.md](./docs/guides/package-selection.md), [docs/guides/lsp.md](./docs/guides/lsp.md).

Do **not** choose, keep, or reject a package because it fits or does not fit the current layout of this repo, the live agent dir, deploy, or an existing sidecar class. Layout is downstream of the pin. If a better package needs a deploy change, a new config root, a greenfield pin, or a refactor of how we land files, do that work. Setup cost, refactor cost, and greenfield cost are not selection criteria.

Sidecar classification below is **how** a chosen package is landed. It is never a reason to keep a weaker package.

Do not install two packages that register the same tool names for the same job.

### Pin form

The `packages` entry is the unversioned source: `npm:<name>` or `git:github.com/<user>/<repo>`. Do not add `@version`, `@tag`, or a git SHA. Unversioned pins move with `pi update --extensions`, and with nothing else. Reasoning and the update ritual: [docs/guides/package-pinning.md](./docs/guides/package-pinning.md).

Pi treats any git ref as frozen, a branch name included, and treats only an exact npm version as frozen. A frozen source never appears in the startup update notice, so a freeze also costs the operator that signal.

Freeze one pin only to hold back a known-bad upstream. Write the reason and the removal condition in the commit message. A freeze with no written expiry is the failure this rule exists to stop.

Which upstream commit the operator actually read is a separate fact from which source to install. It lives in `docs/plugins/<plugin-name>/SPEC.md` as a `Verified against upstream <sha>` line, and it is bumped in a commit after the operator reads the upstream diff. Never put that SHA back into the pin.

### Sidecar config files

This repository is SoT for **every** plugin config. A pin without a classified sidecar list is unfinished. Read upstream docs and the installed source, list every config file the package reads, then land one class per file. If the package reads a path outside the live agent dir, extend deploy to land that path from this clone. Do not reject the package. Do not vendor the package source into this git tree to dodge the path.

Classes:

| Class       | When                                                                                    | This repo                | `just deploy`         |
| ----------- | --------------------------------------------------------------------------------------- | ------------------------ | --------------------- |
| `live-only` | The file can hold tokens or other secrets, or it is a leftover name we refuse to create | absent; gitignored       | do not touch dest     |
| `symlink`   | No secrets, and the runtime may write it                                                | tracked at `home/<path>` | symlink dest → source |
| `copy`      | No secrets, and this repo owns the bytes; the runtime does not write it                 | tracked at `home/<path>` | copy dest from source |

Sensitive wins. A mixed file that can hold API keys **and** policy **and** live UI state is `live-only`, like `auth.json`. Do not symlink it. Do not copy it. Do not keep an example that still looks like it could be the live file.

If the runtime writes the file but refuses a symlink (`O_NOFOLLOW`, atomic `rename` onto the path), keep it owned here and set `followsSymlinks: false`. Deploy lands a **hardlink** (same inode, looks like a regular file). That is the native stand-in for a symlink: TUI reads succeed; an atomic save breaks the hardlink; the next `just deploy` 3-way-syncs dest and source against HEAD, then restores the hardlink. Cross-device trees fall back to copy. Deploy probes one real link before it touches dest, because two btrfs subvolumes report one `st_dev` and still refuse `link()`. Conflict (both sides differ from HEAD) fails deploy until you copy the winner onto the other path.

Legacy names we do not own (`plan-mode.json` for pi-plan-mode) are also `live-only`: gitignore them and never create them here.

Caches (`web-search-cache/`, sessions, npm trees) are not sidecars. They stay live-only and gitignored.

Machine contract: `docs/plugins/<plugin-name>/sidecars.json`. `just doctor` / `just check` prove it. `just deploy` lands `copy` and `symlink` rows from that file.

`path` is relative to `$HOME`, which is what the package actually reads, and the source is tracked at `home/<path>`. A path under `.pi/agent/` lands at `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/<rest>`. Any other path lands at `$HOME/<path>`. There is no `root` key. No `..`.

Do not copy a `symlink` sidecar on every deploy. That clobbers live writes. `copy` plus `followsSymlinks: false` is the hardlink stand-in when the package cannot follow a link. Do not leave a non-secret sidecar unclassified or live-only “until we have a policy”: `{}` in this clone is a managed default.

### Stay in `pi-config`

Keep a resource here when it is:

- personal glue (footer, house style, your `/review` prompt)
- only consumed by you
- edited here, then landed with `just deploy`, then `/reload`

### Extract to a separate repo

Open `pi-<feature>` when it is:

- one idea with its own version, README, and changelog
- something others should install _without_ your settings
- in need of tests, CI, npm publish, or pinned git tags
- carrying dependencies you do not want in the live agent-dir `node_modules`

Rule: if you would name the npm package after the feature, it is its own project. If you would describe it as “how I run Pi,” it stays here.

### What a package may contain

| Thing                               | In `pi-config`        | In `pi-<feature>`                                |
| ----------------------------------- | --------------------- | ------------------------------------------------ |
| `settings.json`, `keybindings.json` | yes (source)          | no                                               |
| `AGENTS.md`                         | yes (yours, deployed) | no (consumers have their own)                    |
| `auth.json`, live `models.json`     | never in git          | never                                            |
| skills / prompts / themes           | yes                   | yes                                              |
| TypeScript extensions               | yes                   | yes                                              |
| `packages` pins                     | your list             | consumers add `npm:@you/pi-<feature>` themselves |

---

## 10. Format of an extracted package repo

Name: `pi-<feature>` npm: `pi-<feature>` or `@<you>/pi-<feature>` keyword: `pi-package`

An extracted package keeps stock names at its own root. It does not mirror `$HOME`. The `home/` mirror is a `pi-config` convention, because `pi-config` lands a whole home directory and a package lands a resource set.

```text
pi-<feature>/
├── README.md
├── LICENSE
├── package.json
├── extensions/                 # if any
│   └── index.ts
├── skills/                     # if any
│   └── <name>/
│       └── SKILL.md
├── prompts/                    # if any
│   └── <name>.md
└── themes/                     # if any
    └── <name>.json
```

`package.json`:

```json
{
  "name": "@<you>/pi-<feature>",
  "version": "0.1.0",
  "keywords": ["pi-package"],
  "pi": {
    "extensions": ["./extensions"],
    "skills": ["./skills"],
    "prompts": ["./prompts"],
    "themes": ["./themes"]
  }
}
```

Include only keys for resources that exist. Paths are relative to the package root. Globs and `!exclusions` are allowed.

Peer the Pi SDK packages if the extension imports them; do not bundle `@earendil-works/pi-ai`, `@earendil-works/pi-agent-core`, `@earendil-works/pi-coding-agent`, `@earendil-works/pi-tui`, or `typebox`.

Test before publish:

```bash
pi -e ./path/to/pi-<feature>
pi install /absolute/path/to/pi-<feature>
```

Ship:

```bash
# npm
npm publish

# git, from a repo that tags its releases
pi install git:github.com/<you>/pi-<feature>
```

Tag the release upstream. Consume it here unversioned, like every other pin. After extract, this source repo consumes it as a pin in `settings.json`. The live file is a symlink, so `pi install` writes the pin here; then `just deploy` is only needed for copied payloads. Do not commit the clone under `git/` or `npm/` here or in the live agent dir.

A subdirectory inside `pi-config` (`packages/pi-foo`) is acceptable while incubating. Do not publish this repository, and do not publish the live agent directory, as “the plugin.”

---

## 11. Principles

1. **One writer per file.** Nix owns the binary and `PI_SKIP_VERSION_CHECK`. This git tree owns authored config. `just deploy` copies static payloads and creates the live symlinks. Pi writes `settings.json` and `keybindings.json` through those links.
2. **This repo is source, not the agent dir.** `home/` mirrors `$HOME` exactly, so a payload's repo path is its home path, and deploy is a copy or a symlink of that path. The root is machinery, and nothing there is ever deployed.
3. **Secrets never enter git or the Nix store.**
4. **Declare installs; ignore trees.** `packages` in source `settings.json` is tracked. Live `npm/`, `git/`, `bin/` are not.
5. **Sessions are state, not config.** They stay in the live agent dir, which is outside this git tree.
6. **Edit here, then deploy copies.** `/settings` and `pi install` mutate the clone through the symlink; commit those. Static payloads still need `just deploy` after you edit them. `/login` is never committed.
7. **Personal glue stays; a named feature leaves.**
8. **Do not market this repo as a drop-in for strangers.** They can read it. They should not `pi install` your home. Host landing is `just deploy` for this operator.
9. **Choose packages for the model, not for the current layout.** The pin is the one that makes the agent more precise, deterministic, and effective, with token-sane tool results. Popularity, maturity, and compatibility with the rest of the stack are clues. The cost of changing this repo is not a selection criterion. Sidecar classification (§9) lands a chosen package; it does not decide which package wins.

---

## 12. Home Manager sketch

Keep the module thin. It installs the executor and does not write the agent directory.

```nix
{
  home.packages = [ pkgs.pi-coding-agent ];
  home.sessionVariables.PI_SKIP_VERSION_CHECK = "1";
  # do not set PI_CODING_AGENT_DIR
  # do not set PI_CODING_AGENT_SESSION_DIR
  # do not set settings / models / context that write into the agent dir
}
```

If you previously used `programs.pi-coding-agent.settings` or `home.file` to materialize agent-dir files, remove that when this repository's justfile becomes the writer.

---

## 13. Workflows

### New machine

1. Install Pi via Nix/Home Manager (binary + PATH helpers only).
2. Clone `pi-config` anywhere in the src tree.
3. `just deploy` (from the clone). This copies static payloads and `copy` sidecars, and symlinks `settings.json`, `keybindings.json`, and `symlink` sidecars into `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`.
4. `/login` (or inject env keys via sops). `auth.json` appears in the live agent dir, mode `0600`.
5. Copy `home/.pi/agent/models.example.json` to live `models.json` if that file is untracked and this machine needs it.
6. Materialize global packages. They are not installed on Pi startup (that auto-install is project `.pi/` only). `pi update --extensions` If a pin is still missing, `pi install` that source from `settings.json` `packages`.
7. Do not copy `sessions/` or `auth.json` from another machine unless you intend to.

If Home Manager used to own files in the agent dir, activate the thinned module **before** `just deploy`. Deploy refuses when `AGENTS.md` or `prompts` is a store symlink.

### Change config

1. Edit the source file in this clone. `/settings` already edits `settings.json` here, through the symlink.
2. Commit if it is a decision you want on every host.
3. `just deploy` if the change was a copied payload. Symlinked files need no redeploy after a commit.

### Incubate then extract

1. Build the extension/skill in `home/.pi/agent/extensions/` or `home/.pi/agent/skills/` here.
2. `just deploy`, then `/reload`.
3. When it deserves its own version, copy to `pi-<feature>` following §10.
4. Replace the local files with a `packages` pin in source `settings.json`.
5. Delete the now-duplicate tree from `pi-config` and deploy.

### Work inside this repo

Pi loads global `AGENTS.md` from the live agent directory **and** from the project cwd. The `home/` mirror makes that safe by construction: the file at the clone root is the clone's own rules, and the payload sits at `home/.pi/agent/AGENTS.md`, where a cwd lookup never finds it. No override file is needed, and the root `AGENTS.md` is never deployed.

---

## 14. Development environment

`flake.nix` and `.envrc` are the source of truth for every tool a recipe or a hook calls by name, and for every language server the agent uses on this tree. `.pre-commit-config.yaml` is the source of truth for the gates themselves. Nix owns the runtimes and those servers; pre-commit owns the hooks. Do not add a language server for a language this repository does not contain.

### Enter the shell

1. `direnv allow` once per clone. After that, `cd` into the clone enters the devShell.
2. `just hooks` to install the git hooks for every stage the config declares.
3. `just devshell-check` proves the shell supplies every tool. A missing tool is a missing line in `flake.nix`, never a reason to install it into the home profile.

A non-interactive context — CI, an agent, an editor task, `bash -c` — does not fire the direnv hook and must wrap the command: `nix develop --command just deploy`.

This includes `git commit`. Most gates run `language: system` and resolve their binary off PATH, so a commit from a plain shell fails with `Executable not found`. Commit from the devShell, or wrap it: `nix develop --command git commit`. Never pass `--no-verify`.

### Gates

| Stage        | What runs                                                                   |
| ------------ | --------------------------------------------------------------------------- |
| `pre-commit` | formatting, linting, staged-diff secrets, and `just check`                  |
| `commit-msg` | `committed`, over `committed.toml`                                          |
| `pre-push`   | `gitleaks` over the whole history, `lychee` over the markdown, `just check` |

`just check` is the repository's own contract, and a hook calls it. It refuses a tracked secret, an uncovered `.gitignore` line, a pin without its `docs/plugins/<name>/` set, and an unclassified sidecar. `just lint` runs every gate over the whole tree by hand.

The Conventional Commits grammar belongs to the configured global `commit-msg` hook, not to this repository. `committed` adds only what that hook leaves alone: subject and body length, lower case after the colon, and no trailing period.

A hook whose upstream language is rust, go, or python with a prebuilt wheel runs `language: system` and takes its binary from the devShell. Such a wheel ships a dynamically linked binary whose ELF interpreter `/lib64/ld-linux-x86-64.so.2` does not exist on a Nix host. The `rev` pins the hook definition; `flake.nix` pins the binary.

### Who owns a file's bytes

dprint is the formatter of record for markdown and JSON, with `textWrap: "never"`. Prose is one physical line per paragraph.

`dprint.json` excludes the JSON that Pi writes at runtime, all of it under `home/.pi/agent/`: `settings.json`, `keybindings.json`, `pi-plan-mode.json`, `pi-review.json`, `99extensions.json`, `intercom/config.json`, and `extensions/**/config.json`. Two reasons. Pi rewrites those files itself, so a formatter fights the runtime on every write. A formatter also replaces a file atomically, which breaks the hardlink a `followsSymlinks: false` sidecar depends on (§9).

The three whitespace fixers in `.pre-commit-config.yaml` carry the same exclude list, under the YAML anchor `runtime_owned`, anchored on the same `home/.pi/agent/` prefix. Pi writes `settings.json` with no trailing newline. A fixer that adds one is undone on Pi's next write, and the two trade that byte forever. Add a new runtime-written file to both lists at once.

If a hook ever rewrites a landed sidecar, the next step is `just deploy`. It 3-way-syncs the file and restores the hardlink.

---

## 15. Anti-patterns

- Home Manager `home.file` or a settings seed into the agent dir
- Exporting `PI_CODING_AGENT_DIR` at this clone, including at `home/.pi/agent` inside it
- Cloning this repository onto `~/.pi/agent`, or symlinking `home/.pi/agent` onto the live dir
- Deploying the root `AGENTS.md`, `auth.json`, or session transcripts
- Putting a payload file anywhere but `home/`, or repo machinery anywhere but the root
- Committing `auth.json` because “it is config”
- Vendoring live `npm/` or `git/` into this git tree
- Choosing or rejecting a package because it would require a deploy, sidecar, or layout refactor
- Adding `@version`, `@tag`, or a git SHA to a `packages` pin, outside a freeze that holds back a known-bad upstream
- Freezing a pin without writing its reason and its removal condition in the commit message
- Recording the audited upstream commit in the pin instead of in `docs/plugins/<name>/SPEC.md`
- Leaving a plugin pin without `docs/plugins/<name>/sidecars.json`
- Treating the live agent dir as SoT for a non-secret plugin sidecar
- Symlinking a sidecar that can hold tokens
- Copying a runtime-writable sidecar on every `just deploy` unless that package refuses symlinks (`followsSymlinks: false` hardlink)
- Gitignoring a `copy` or `symlink` sidecar
- Putting skills in a non-standard folder without listing it in `settings.json`
- Publishing this repository as the public package others should install to “get your setup”
- Naming extracted packages `pi-plugins` or leaving them unnamed inside `extensions/` after they have users of their own
- Installing a gate's tool into the home profile instead of adding it to `flake.nix`
- Letting a formatter rewrite a sidecar Pi writes at runtime
- Passing `--no-verify`

---

## 16. Decision log

- Home Manager is not SoT for the live agent directory.
- This repository is source, not the live agent directory.
- `just deploy` lands owned files at `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`, which is the path Pi already reads. This project does not set that variable.
- Copied payloads: `AGENTS.md`, prompts, skills, extensions, themes, and plugin sidecars classified `copy`.
- Symlinked (runtime writes, this repo tracks): `settings.json`, `keybindings.json`, and plugin sidecars classified `symlink`.
- Auth lives at the live agent dir `auth.json` and is never linked.
- This clone is SoT for every plugin config. Classify each sidecar from upstream docs. Sensitive or mixed-secret files are `live-only`. `web-search.json` is live-only because it can hold keys and curator state.
- ~~Repo root uses Pi’s conventional layout so deploy is a copy or a symlink of those names.~~ Superseded below.
- Sessions and package install trees stay in the live dir, off git.
- Shareable add-ons are packages named `pi-<feature>`, usually separate repositories.
- The repository name is `pi-config`.
- Global `packages` pins are SoT in source `settings.json`. `just check` / `just doctor` prove each pin has `docs/plugins/<name>/` (README, SPEC, sidecars.json) and that each sidecar class is landed. `just status` reports live trees and sidecar dest state. Missing trees are notes, not doctor failures. Names are derived from pins; recipes do not hardcode plugin ids.
- Package selection is effectiveness-first (precision, determinism, token-sane tools). Fit to the current pi-config layout is not a criterion and must not become one. Popularity, maturity, and compatibility are clues. Setup, refactor, and greenfield cost are not vetoes.
- Pins are unversioned. The audited upstream commit lives in `docs/plugins/<name>/SPEC.md`, not in the pin. A freeze holds back a known-bad upstream and carries a written removal condition. Reasoning: [docs/guides/package-pinning.md](./docs/guides/package-pinning.md).
- Reversed: pointing `PI_CODING_AGENT_DIR` at the clone, and treating the clone as the directory Pi mutates.
- `flake.nix` and `.envrc` supply the toolchain; `.pre-commit-config.yaml` holds the gates. The two never merge: no `git-hooks.nix`, no `flake-parts`, no `treefmt-nix`. A gate is readable without evaluating Nix, and the shell is buildable without running a gate.
- dprint formats markdown and JSON, except the JSON Pi writes at runtime. The runtime owns the bytes of a file it writes.
- Supersedes the repo-root-layout entry above: the payload lives under `home/`, a literal `$HOME` mirror, and the root is machinery only. A payload's repo path states its own destination, so deploy is still a copy or a symlink of that path. This also ends the `AGENTS.md` double injection structurally, because a cwd lookup at the clone root now finds the clone's own rules and never the payload. `AGENTS.override.md` is deleted.
- A sidecar `path` in `docs/plugins/<name>/sidecars.json` is relative to `$HOME` and is tracked at `home/<path>`. The `root` key is gone: a path under `.pi/agent/` follows `PI_CODING_AGENT_DIR`, and anything else lands under `$HOME`.
