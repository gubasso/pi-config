# pi-sandbox landing

Verified against upstream `f1acc3784d8f8ce94fb64ed81ba849e011e5cb6c`, tag v0.8.2 (`index.ts`, `src/config.ts`, `src/sandbox-runtime.ts`, `src/policy.ts`, `src/extension.ts`, `src/ui.ts`, README), and the npm tarball of its dependency `@carderne/sandbox-runtime` 0.0.80 (`dist/sandbox/linux-sandbox-utils.js`, `dist/sandbox/sandbox-manager.js`). The npm tree of `pi-sandbox@0.8.2` matches the tag file for file.

## Pin and tree

| Artifact     | This repo                                                    | Live                                                                        |
| ------------ | ------------------------------------------------------------ | --------------------------------------------------------------------------- |
| Pin          | `settings.json` `packages` → `npm:pi-sandbox@0.8.2` (frozen) | symlink already                                                             |
| Install tree | no                                                           | `npm/node_modules/pi-sandbox`, `npm/node_modules/@carderne/sandbox-runtime` |

`package.json` declares one extension, `./index.ts`. The package ships no skill, prompt, or theme. It declares `@earendil-works/pi-coding-agent` `^0.80.0` as an optional peer. Pi 1.5.2 loads it, and the sandbox starts.

`just deploy` lands the pin and `sandbox.json`, and it installs nothing. Run `pi install npm:pi-sandbox@0.8.2` once after the deploy.

## External requirement

The runtime needs `rg`, `bwrap`, and `socat` on the `PATH` that pi starts with. Without one of them, the sandbox does not start, and pi shows `Sandbox initialization failed`. On this host, `rg` comes from the home profile, and `bwrap` and `socat` come from the host packages in `/usr/bin`. The runtime also runs its own `vendor/seccomp/<arch>/apply-seccomp` binary from the install tree.

## Sidecars

Resolver (`src/config.ts`): `getConfigPaths` joins `getAgentDir()` and `sandbox.json` for the global file, and the session folder, `.pi`, and `sandbox.json` for the project file. `loadConfig` reads both on every tool call. A missing file means the built-in defaults. The project file loads only when pi trusts the project.

pi-sandbox writes the global file when a person picks "Allow for all projects" in a permission prompt. `writeConfigFile` calls `writeFileSync` on the path, which follows a symlink. So the write lands in this repository, and `git diff` shows it.

| Artifact                 | Class     | Why                                                    |
| ------------------------ | --------- | ------------------------------------------------------ |
| `.pi/agent/sandbox.json` | `symlink` | No secrets. The package writes it in place on a grant. |

The project file `<session folder>/.pi/sandbox.json` belongs to each project, not to this clone.

## Merge rules

Each array of the global file replaces its built-in default as a whole. The arrays of the global file and the project file are combined. So this clone controls every default, with one exception: on Linux, pi-sandbox always adds the folder of the runtime's seccomp helper to the bash read paths.

The built-in defaults that this landing replaces:

| Key          | Default                                 | This landing                                   |
| ------------ | --------------------------------------- | ---------------------------------------------- |
| `allowRead`  | `.`, `~/.config`, `~/.local`, `Library` | `.` and named tool paths, no whole `~/.config` |
| `denyRead`   | `/Users`, `/home`                       | `/home`, then literal secret and socket paths  |
| `allowWrite` | `.`, `/tmp`                             | unchanged                                      |
| `denyWrite`  | `.env`, `.env.*`, `*.pem`, `*.key`      | the defaults, then the two paths of this file  |

`network` keeps its defaults: ten package and GitHub domains. A localhost URL is not on the list, so a command cannot reach a local gateway.

## How each tool is checked

### Bash

Each command runs in bubblewrap. The root is read-only. `.` and `/tmp` are bound writable.

- A `denyRead` folder gets a tmpfs over it. Each `allowRead` path under it is bound back. The runtime applies the folders shallow first, so a deeper deny lands after the bind-back of its parent.
- A `denyRead` file gets `/dev/null` bound over it. Only an exact `allowRead` entry for that file undoes the mask. A folder entry does not, so `.envrc.local` stays masked inside an allowed project folder.
- A deny path that does not exist when the command starts is skipped.
- A seccomp filter blocks `socket(AF_UNIX)`, so no command opens a Unix socket, listed or not. The network namespace is private, and a proxy filters every connection by domain.
- A write under a tmpfs succeeds, but it lands in the tmpfs and never reaches the host.

### Built-in read

The `tool_call` hook resolves the path and compares it with `allowRead` and `allowWrite` only. It never reads `denyRead`. A path outside the allow lists prompts in the TUI and is blocked in every other mode. A path inside them is read with no prompt, even when `denyRead` names it.

### Built-in write and edit

`decideWritePolicy` denies a `denyWrite` match with no prompt. It allows an `allowWrite` match and prompts for the rest. Globs work here.

### Extension and MCP tools

No check. They run in the pi process.

## Findings that shape the file

- `denyWrite` lists the repository source of this file before the live link `~/.pi/agent/sandbox.json`. Both spellings resolve to one file, and `@carderne/sandbox-runtime` 0.0.80 keeps the first one. When the live link comes first, the runtime tests the link spelling, finds it under the `/home` tmpfs, and drops the bind. The source then stays writable from a session in this repository. The order shown keeps the bind.
- `/run/user/1000` holds more credential sockets than the first list named: `gnupg`, `ssh-agent.socket`, `kwallet5.socket`, the KeePassXC browser socket, `forge-auth`, and `cc-socks`. `denyRead` names each one.
- No `wayland-*` socket existed on 2026-11-25, and neither did `podman` or `kitty` in `/run/user/1000`. `denyRead` keeps `podman` and `kitty`, and they apply once they exist.
- A linked worktree fails `git` in bash, because its `.git` file points into the main checkout, outside the allow list. Grant the main `.git` for one session with `/sandbox-allow`.

## The login file

pi reads `~/.pi/agent/auth.json` in its own process, outside the sandbox, so the guard never blocks its login. Bash sees the file as a masked device, and a read of it fails with `Permission denied`. The built-in read tool prompts for it, because no allow entry covers it. A person can still grant that prompt.

## Upkeep

The literal lists go stale. Add each new `.envrc.local` under `~/Projects` to `denyRead`, and remove each one that is gone. The `/tmp/kitty-*` entries name the sockets of 2026-11-25. Old windows keep their sockets until they restart, and the seccomp filter blocks the new ones. Remove the old entries after every kitty window restarts with the socket in `/run/user/1000/kitty`.

After a change, restart the pi sessions. A running session keeps its bash rules until it restarts.
