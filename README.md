# pi-config

Source tree for one operator's global [Pi Coding Agent](https://pi.dev) config.
It is not the live agent directory. Live files are
`${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`.

Nix installs the `pi` binary. This project does not set
`PI_CODING_AGENT_DIR`. `just deploy` lands owned files there in two
ways:

- **Copy** — static payloads Pi only reads (`AGENTS.md`, `prompts/`,
  …) and plugin sidecars classified `copy`.
- **Symlink** — files the runtime mutates that this repo still tracks
  (`settings.json`, `keybindings.json`, plugin sidecars classified
  `symlink`). `/settings`, `pi install`, and plugin Settings writes
  go through into git.

`/login` writes live `auth.json` (mode `0600`). Secret plugin
sidecars stay live-only. Those files are never symlinked and never
enter git.

Layout, tracking, secrets, and extract rules: [SPEC.md](./SPEC.md).
Install a third-party package:
[docs/guides/install-packages.md](./docs/guides/install-packages.md).
Per-package notes: [docs/plugins/](./docs/plugins/README.md).

## Commands

- `just deploy` — copy static payloads and `copy` sidecars; symlink live-writable tracked files
- `just doctor` — prove the source tree, plugin docs, sidecar classes, and the landing when dest exists
- `just status` — show source, dest, live files, and each pin vs docs vs tree
- `just check` — source-tree proofs (safe without a host landing)
