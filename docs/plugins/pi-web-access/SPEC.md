# pi-web-access landing

Verified against installed 0.29.0 on this host.

## Pin and tree

| Artifact | This repo | Live |
| --- | --- | --- |
| Pin | `settings.json` `packages` → `npm:pi-web-access` | symlink already |
| Install tree | no | `npm/node_modules/pi-web-access` |

## Sidecar

Live path when `PI_CODING_AGENT_DIR` is unset:
`$HOME/.pi/agent/web-search.json`.

Resolver (`utils.ts`): `PI_CODING_AGENT_DIR` first; else existing
`XDG_CONFIG_HOME/pi/web-search.json`; else existing legacy
`~/.pi/web-search.json`; else `~/.pi/agent`. New files go in the
agent dir when neither env is set.

The file is mixed:

| Layer | Examples | Who writes |
| --- | --- | --- |
| Secrets | `*ApiKey`, `searxngHeaders`, auth-fetch profiles | operator |
| Policy | `searchRouting`, `workflow`, `tools`, `ssrf`, `shortcuts` | operator |
| Live state | `/curator` on/off, curator provider dropdown | the package |

Keys may be literals, `$NAME` / `${NAME}`, or `!/path/to/cmd`.
Env vars such as `BRAVE_API_KEY` override literals. The package
does not echo file text on parse errors.

Cache: live `web-search-cache/`. Never git.

## Class

| Artifact | Class |
| --- | --- |
| `web-search.json` | live only, mode `0600` if created; gitignored |
| `web-search.example.json` | not yet (no shared policy) |
| `web-search-cache/` | live only; gitignored |

Do not symlink live `web-search.json` while it can hold literal
keys and while `/curator` would dirty this clone. Do not copy it
on every `just deploy`.

Create the live file only when adding keys or routing. After
install, `/reload` or start a new session.
