# pi-config

Source tree for one operator's global [Pi Coding Agent](https://pi.dev) config. It is not the live agent directory. Live files are `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`.

Nix installs the `pi` binary. This project does not set `PI_CODING_AGENT_DIR`. `just deploy` lands owned files there in two ways:

- **Copy** — static payloads Pi only reads (`AGENTS.md`, `prompts/`, …) and plugin sidecars classified `copy`.
- **Symlink** — files the runtime mutates that this repo still tracks (`settings.json`, `keybindings.json`, plugin sidecars classified `symlink`). `/settings`, `pi install`, and plugin Settings writes go through into git.

`/login` writes live `auth.json` (mode `0600`). Secret plugin sidecars stay live-only. Those files are never symlinked and never enter git.

## Documentation

| Document                                                          | What it answers                          |
| ----------------------------------------------------------------- | ---------------------------------------- |
| [SPEC.md](./SPEC.md)                                              | Layout, tracking, secrets, extract rules |
| [guides/harness-selection.md](./docs/guides/harness-selection.md) | Which agent binary this operator runs    |
| [guides/package-selection.md](./docs/guides/package-selection.md) | Which package wins for a job             |
| [guides/install-packages.md](./docs/guides/install-packages.md)   | How to land a third-party package        |
| [guides/lsp.md](./docs/guides/lsp.md)                             | The LSP pin                              |
| [plugins/](./docs/plugins/README.md)                              | Per-package landing notes                |

## Getting started

```sh
git clone https://github.com/gubasso/pi-config.git
cd pi-config
direnv allow      # enters the devShell from flake.nix
just devshell-check
just hooks        # install the git hooks for every stage
just deploy
```

`direnv allow` is a one-time step per clone. Without direnv, wrap each command: `nix develop --command just deploy`.

## Commands

- `just deploy` — copy static payloads and `copy` sidecars; symlink live-writable tracked files
- `just doctor` — prove the source tree, plugin docs, sidecar classes, and the landing when dest exists
- `just status` — show source, dest, live files, and each pin vs docs vs tree
- `just check` — source-tree proofs (safe without a host landing)
- `just hooks` — install the pre-commit, commit-msg, and pre-push hooks
- `just lint` — run every gate over the whole tree
- `just devshell-check` — prove the devShell supplies every tool a recipe or a hook calls

Tooling and gates: [SPEC.md](./SPEC.md) §14.
