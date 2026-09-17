# pi-lsp-client landing

Verified against upstream `1c981dfcacc456fe4ce9f4120a2f0250b54d6844` (`src/lsp/config-loader.ts`, `src/lsp/constants.ts`, `src/index.ts`, README).

## Pin and tree

| Artifact     | This repo                                                                              | Live                                        |
| ------------ | -------------------------------------------------------------------------------------- | ------------------------------------------- |
| Pin          | `settings.json` `packages` → `git:github.com/code-yeongyu/pi-lsp-client` (unversioned) | symlink already                             |
| Install tree | no                                                                                     | `git/github.com/code-yeongyu/pi-lsp-client` |

## Sidecars

Resolver (`src/lsp/config-loader.ts` `getConfigPaths`):

| Path                        | Scope                | This clone                               |
| --------------------------- | -------------------- | ---------------------------------------- |
| `$HOME/.pi/lsp-client.json` | user-global          | classified, landed                       |
| `<cwd>/.pi/lsp-client.json` | trusted project, cwd | not a global sidecar; do not create here |

`loadJsonFile` only reads. A missing file is valid: builtins from `BUILTIN_SERVERS` apply. A parse error is treated as missing. The package never writes either path.

Project config wins over user config over builtins. `disabled: true` removes a builtin. An entry without `command` and `extensions` is ignored except for `disabled`.

Source `home/.pi/lsp-client.json` adds servers this tree needs that are not pi-lsp-client builtins: `jsonls` (`.json`/`.jsonc`), `taplo` (`.toml`), `marksman` (`.md`). `biome` is disabled so it cannot claim JSON (dprint owns format here). Other builtins stay. `pyright`, `ruff`, `nixd`, `yaml-language-server`, and `bash-language-server` are PATH probes from the flake, not entries here.

Do not run `/lsp install`. Servers are PATH probes (`src/lsp/server-installation.ts`). Auto-install recipes stay unused.

Result caps (`src/lsp/constants.ts`): 200 references, 200 symbols, 200 diagnostics, 50 directory files.

Cache: none under the agent dir. Language-server processes are session-lifetime, reaped on idle and `session_shutdown`.

## Class

| Artifact              | Class  | Why                                                                    |
| --------------------- | ------ | ---------------------------------------------------------------------- |
| `.pi/lsp-client.json` | `copy` | No secrets; package only reads it. Dest is `$HOME/.pi/lsp-client.json` |

After install, `/reload` or start a new session.
