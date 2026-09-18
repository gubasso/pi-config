# pi-model-fallback-alias landing

Verified against published 0.2.0 (`index.ts`, `src/alias-config.ts`, `src/fallback/config.ts`, `src/state-paths.ts`, `package.json`, README), which is upstream commit `b3ebd22444b86919cb79ff34aa38b094a4062545`.

## Pin and tree

| Artifact     | This repo                                                  | Live                                       |
| ------------ | ---------------------------------------------------------- | ------------------------------------------ |
| Pin          | `settings.json` `packages` → `npm:pi-model-fallback-alias` | symlink already                            |
| Install tree | no                                                         | `npm/node_modules/pi-model-fallback-alias` |

`package.json` declares one entry point, `index.ts`, under the `pi.extensions` key. The package ships no skill, prompt, or theme. Development peers were `@earendil-works/pi-ai` 0.84.4, `pi-coding-agent` 0.84.4, `pi-tui` 0.85.1. Runtime peers are optional `*`.

## Why this pin

Checklist row B, omp model roles. The package that won under [package-selection.md](../../guides/package-selection.md): named `alias/<role>` models with ordered target chains, failover before any text or tool output commits, shared cooldowns, and target auth resolved through Pi's registry. Rename-only aliases (`@zigai/pi-model-alias`) lost because they do not create lanes. Per-turn routers (`@yeliu84/pi-model-router`) lost because they classify every turn and are not deterministic. 429 cyclers that call `setModel` lost because Pi persists that switch as the global default.

`pi-subagents` `agentOverrides.<name>.model` already pins a child to a concrete id. This package is the shared name the parent `/model` picker and those overrides can both use once a second model exists.

## Sidecars

Live path when `PI_CODING_AGENT_DIR` is unset: `$HOME/.pi/agent/model-alias.json`.

Resolver (`src/alias-config.ts`): `PI_MODEL_ALIAS_MAP` if set, else `getAgentDir()` then `model-alias.json`. Missing or invalid file registers no aliases (`index.ts` returns when the map is empty). The package never writes this file. Per-stream policy re-reads it; a broken edit keeps the last valid policy and warns.

The file is policy, not secrets:

| Layer      | Examples                                       | Who writes |
| ---------- | ---------------------------------------------- | ---------- |
| Policy     | role keys, target chains, `$defaults` timeouts | operator   |
| Live state | none in this file                              | —          |

Keys that start with `$` are metadata except `$settings` and `$defaults`, which the parser owns. Nested `alias/<role>` targets flatten at load. Concrete targets are `provider/model` strings.

## Runtime state, not a sidecar

`src/state-paths.ts`: `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/state/pi-model-fallback-alias/` unless `PI_MODEL_ALIAS_STATE_DIR` is set.

| Path                         | What it is                               |
| ---------------------------- | ---------------------------------------- |
| `cooldown-state.json`        | shared target cooldown, atomic replace   |
| `pi-model-alias-debug.jsonl` | rotating latency and troubleshooting log |

Logs record role names, target refs, durations, status codes, and allowlisted request ids. They do not record credentials, payloads, or the alias map. This clone does not land the directory. `.gitignore` covers `/home/.pi/agent/state/`.

The alias provider returns a fixed non-secret API-key value only so Pi marks the models available. Streaming discards it and authenticates the selected target through the registry. Forwarded requests drop caller `authorization`, `x-api-key`, `api-key`, `x-goog-api-key`, and `anthropic-*` headers.

## Source sidecar

`home/.pi/agent/model-alias.json` registers the ten omp built-in roles from `packages/coding-agent/src/config/model-roles.ts`. Leaf roles (`default`, `smol`, `slow`, `vision`) target `xai/grok-4.6`. Nested roles follow omp inheritance: `tiny`, `task`, and `commit` flatten to `alias/smol`; `plan`, `designer`, and `advisor` flatten to `alias/slow`. Length-1 leaf chains are identity routing. Append another `provider/model` on a leaf when that model is authenticated. Do not change `settings.json` `defaultProvider` / `defaultModel`, and do not point `subagents.agentOverrides` at `alias/*`, until a leaf chain has two usable targets.

| Role       | omp lane                           | This map       |
| ---------- | ---------------------------------- | -------------- |
| `default`  | parent turns                       | `xai/grok-4.6` |
| `smol`     | cheap fan-out                      | `xai/grok-4.6` |
| `slow`     | deep reasoning                     | `xai/grok-4.6` |
| `vision`   | image input                        | `xai/grok-4.6` |
| `tiny`     | titles, memory; falls back to smol | `alias/smol`   |
| `task`     | subtask                            | `alias/smol`   |
| `commit`   | commit and changelog               | `alias/smol`   |
| `plan`     | plan mode                          | `alias/slow`   |
| `designer` | design                             | `alias/slow`   |
| `advisor`  | second-pass review                 | `alias/slow`   |

Commands after `/reload`: `/model-alias-targets`, `/model-alias-latency-report`, `/model-alias-reset-cooldown`.

## Class

| Artifact                     | Class  | Why                                       |
| ---------------------------- | ------ | ----------------------------------------- |
| `.pi/agent/model-alias.json` | `copy` | No secrets, and the package only reads it |

## Interaction with the other pins

The package registers provider id `alias` and slash commands `model-alias-reset-cooldown`, `model-alias-targets`, `model-alias-latency-report`. No other pin in `settings.json` uses those names.

`pi-subagents` still resolves one model per launch and does not walk these chains. Point a child at `alias/smol` only after that role has a cheap concrete target.

After install, `/reload` or start a new session.
