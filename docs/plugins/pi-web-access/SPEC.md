# pi-web-access landing

Verified against installed 0.29.0 and upstream README <https://github.com/nicobailon/pi-web-access> (config lives in `web-search.json`).

## Pin and tree

| Artifact     | This repo                                        | Live                             |
| ------------ | ------------------------------------------------ | -------------------------------- |
| Pin          | `settings.json` `packages` → `npm:pi-web-access` | symlink already                  |
| Install tree | no                                               | `npm/node_modules/pi-web-access` |

## Sidecars

Live path when `PI_CODING_AGENT_DIR` is unset: `$HOME/.pi/agent/web-search.json`.

Resolver (`utils.ts`): `PI_CODING_AGENT_DIR` first; else existing `XDG_CONFIG_HOME/pi/web-search.json`; else existing legacy `~/.pi/web-search.json`; else `~/.pi/agent`. New files go in the agent dir when neither env is set. Missing file is valid (zero-config Exa MCP / Codex auth).

The file is mixed:

| Layer      | Examples                                                  | Who writes  |
| ---------- | --------------------------------------------------------- | ----------- |
| Secrets    | `*ApiKey`, `searxngHeaders`, auth-fetch profiles          | operator    |
| Policy     | `searchRouting`, `workflow`, `tools`, `ssrf`, `shortcuts` | operator    |
| Live state | `/curator` on/off, curator provider dropdown              | the package |

Keys may be literals, `$NAME` / `${NAME}`, or `!/path/to/cmd`. Env vars such as `BRAVE_API_KEY` override literals.

Cache: live `web-search-cache/`. Not a sidecar. Never git.

## Class

| Artifact          | Class       | Why                                                                 |
| ----------------- | ----------- | ------------------------------------------------------------------- |
| `web-search.json` | `live-only` | Can hold tokens; runtime also writes curator state. Sensitive wins. |

Do not create `web-search.json` in this clone. Create the live file only when adding keys or routing, mode `0600`. After install, `/reload` or start a new session.
