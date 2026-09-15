# pi-config

Source tree for one operator's global [Pi Coding Agent](https://pi.dev) config.
It is not the live agent directory. Live files are
`${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`.

Nix installs the `pi` binary. This project does not set
`PI_CODING_AGENT_DIR`. `just deploy` copies owned files into the
directory Pi already reads. `just deploy --settings` overwrites live
`settings.json` from git.

`/login` writes live `auth.json` (mode `0600`). That file never enters
git.

Layout, tracking, secrets, and extract rules: [SPEC.md](./SPEC.md).

## Commands

- `just deploy` — copy owned artifacts into the live agent directory
- `just doctor` — prove the source tree, and the landing when dest exists
- `just status` — show source, dest, and whether live files exist
- `just check` — source-tree proofs (safe without a host landing)
