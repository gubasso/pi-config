# pi-config

Source tree for one operator's global [Pi Coding Agent](https://pi.dev) config. It is not the live agent directory. Live files are `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`.

The payload lives under `home/`, which mirrors `$HOME`. A payload's repo path therefore states its own destination: `home/.pi/agent/settings.json` lands at the live agent dir, and `home/.pi/lsp-client.json` lands at `$HOME/.pi/lsp-client.json`. The repo root holds machinery only, and nothing outside `home/` is deployed.

Nix installs the `pi` binary. This project does not set `PI_CODING_AGENT_DIR`. `just deploy` lands owned files in two ways:

- **Copy** — static payloads Pi only reads (`home/.pi/agent/AGENTS.md`, `home/.pi/agent/prompts/`, …) and plugin sidecars classified `copy`.
- **Symlink** — files the runtime mutates that this repo still tracks (`home/.pi/agent/settings.json`, `keybindings.json`, plugin sidecars classified `symlink`). `/settings`, `pi install`, and plugin Settings writes go through into git.

`/login` writes live `auth.json` (mode `0600`). Secret plugin sidecars stay live-only. Those files are never symlinked and never enter git.

## The pi sandbox guard

A pi session handles no secret and reaches no credential gateway. That rule holds until a wrap of pi in sandbox-runtime (`srt`) is specified, tested, and landed. Until then, [pi-sandbox](./docs/plugins/pi-sandbox/README.md) 0.8.2 is the interim guard. Its policy is `home/.pi/agent/sandbox.json`. The guard is partial, and no deny in it is a hard block for every tool.

- Bash tool and `!` commands: each command runs in bubblewrap. The whole home folder is hidden except the session folder and a short list of tool paths. Each secret path and each escape socket in `denyRead` is masked. A seccomp filter blocks every new Unix socket, and a proxy limits the network to the allowed domains. Writes reach only the session folder and `/tmp`, and never the project's `.pi` folder, so a session cannot change its own rules.
- Built-in `read`: pi-sandbox allows the paths in `allowRead` and `allowWrite`, and it prompts for every other path. It ignores `denyRead`. So a secret inside an allowed path, such as a project's `.envrc.local`, is read with no prompt. A person can also grant a prompt for any path.
- Built-in `write` and `edit`: `denyWrite` blocks with no prompt, and paths outside `allowWrite` prompt.
- Extension tools and MCP tools: no guard. They run in the pi process, outside bubblewrap.
- The pi process itself: no guard. It reads its own login file `~/.pi/agent/auth.json`. Commands that pi runs see that file masked.

`just deploy` rewrites the host-specific literals of the policy, and `just doctor` fails when a project `.envrc.local` is not denied. The limits are in the [plugin SPEC](./docs/plugins/pi-sandbox/SPEC.md).

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

`direnv allow` is a one-time step per clone. Without direnv, wrap each command: `nix develop --command just deploy`. [`host-requirements.toml`](./host-requirements.toml) lists the tools that the host supplies.

## Commands

- `just deploy` — converge the live agent dir: copy static payloads and `copy` sidecars, symlink live-writable tracked files, and remove what this repo no longer declares
- `just deploy-report` — the same, but print what would be removed and remove nothing
- `just deploy-adopt` — the same, and also remove files a plain deploy only reports as unmanaged
- `just doctor` — prove the source tree, plugin docs, sidecar classes, and the landing when dest exists
- `just status` — show source, dest, live files, and each pin vs docs vs tree
- `just check` — source-tree proofs (safe without a host landing)
- `just test` — run the tests a commit must pass
- `just test-slow` — run the tests a push must pass
- `just hooks` — install the pre-commit, commit-msg, and pre-push hooks
- `just lint` — run every gate over the whole tree
- `just devshell-check` — prove that the devShell, uv.lock, and package-lock.json put every tool a recipe, a hook, or a language server calls on PATH

Tooling and gates: [SPEC.md](./SPEC.md) §14. Module layout: §15. Tests: §16 and [docs/guides/testing.md](./docs/guides/testing.md).
