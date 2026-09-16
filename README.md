# pi-config

Source tree for one operator's global [Pi Coding Agent](https://pi.dev) config.
It is not the live agent directory. Live files are
`${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`.

Nix installs the `pi` binary. This project does not set
`PI_CODING_AGENT_DIR`. `just deploy` lands owned files there in two
ways:

- **Copy** — static payloads Pi only reads (`AGENTS.md`, `prompts/`, …).
- **Symlink** — files Pi mutates that this repo still tracks
  (`settings.json`, `keybindings.json`). `/settings` and `pi install`
  write through into git.

`/login` writes live `auth.json` (mode `0600`). That file is never
symlinked and never enters git.

Layout, tracking, secrets, and extract rules: [SPEC.md](./SPEC.md).
Install a third-party package:
[docs/guides/install-packages.md](./docs/guides/install-packages.md).
Per-package notes: [docs/plugins/](./docs/plugins/README.md).

## Commands

- `just deploy` — copy static payloads; symlink live-writable tracked files
- `just doctor` — prove the source tree, and the landing when dest exists
- `just status` — show source, dest, and whether live files exist
- `just check` — source-tree proofs (safe without a host landing)
