# pi-intercom landing

Verified against npm `pi-intercom` 0.13.0 (`config.ts`, `broker/paths.ts`, `broker/broker.ts`, `broker/spawn.ts`, `broker/extension-state.ts`) and upstream <https://github.com/nicobailon/pi-intercom>.

## Pin and tree

| Artifact     | This repo                                      | Live                           |
| ------------ | ---------------------------------------------- | ------------------------------ |
| Pin          | `settings.json` `packages` → `npm:pi-intercom` | symlink already                |
| Install tree | no                                             | `npm/node_modules/pi-intercom` |

The package ships one extension and one skill (`skills/pi-intercom`). Both load from the install tree. This repo owns neither.

## Sidecars

Live paths when `PI_CODING_AGENT_DIR` is unset, under `$HOME/.pi/agent/`.

Resolver (`broker/paths.ts`): `getAgentDirPath()` then `intercom/`. `getConfigPath()` appends `config.json`. A missing file loads the package defaults. No code path writes `config.json`. `loadConfig` is the only reader, and it throws when a key has the wrong type.

The package creates `intercom/` with mode `0700` and writes runtime files there with mode `0600`:

| Path                         | What it is                            |
| ---------------------------- | ------------------------------------- |
| `intercom/broker.sock`       | Unix socket the broker listens on     |
| `intercom/broker.pid`        | Broker process id                     |
| `intercom/broker.spawn.lock` | Spawn race lock                       |
| `intercom/broker.port.json`  | Windows TCP endpoint, read by clients |
| `intercom/broker-launch.vbs` | Windows hidden launcher               |
| `intercom/pending-asks/`     | Unresolved `ask` records              |
| `intercom/extension-state/`  | Broker-held extension state           |

Those are runtime state, not config. They stay in the live agent dir and are gitignored here. Messages themselves are not logged. They land in Pi session history, which is live-only already.

## Class

| Artifact                    | Class       | Why                                       |
| --------------------------- | ----------- | ----------------------------------------- |
| `intercom/config.json`      | `copy`      | No secrets, and the package only reads it |
| `intercom/broker.port.json` | `live-only` | Runtime endpoint we refuse to create      |

## Policy in the source sidecar

```json
{
  "enabled": true,
  "inboundTrigger": "replies",
  "confirmSend": true,
  "replyHint": true
}
```

- `inboundTrigger: "replies"` narrows the upstream `"always"` default. An inbound message still renders inline, but only an answer to a question this session asked starts a turn. A peer cannot drive this session uninvited.
- `confirmSend: true` prompts before a non-reply send from an interactive session. This matches the global rule in `AGENTS.md`.
- `brokerCommand` and `brokerArgs` stay unset. The defaults are `npx` and `["--no-install", "tsx"]`, and `tsx` is a dependency of the install tree.
- `stableId` stays unset. This file is global, so a value here pins every session on the host to one intercom id.
- `status` stays unset. It is per-session prose, not host policy.

## Identity

`/alias <name>` calls `pi.setSessionName(name)`. Pi 0.85.1 renders that name in the footer after the working directory (`dist/modes/interactive/components/footer.js`). Peers address the alias. Without an alias, the broker assigns a runtime id such as `subagent-chat-1a2b3c4d`.

## Environment

The package reads `PI_INTERCOM_SCOPE_ID`, `PI_INTERCOM_ASK_TIMEOUT_MS`, `PI_INTERCOM_STABLE_ID`, `PI_INTERCOM_LIVENESS_INTERVAL_MS`, `PI_INTERCOM_LIVENESS_TIMEOUT_MS`, and `PI_INTERCOM_TRANSPORT`. This repo sets none of them. Nix sets none of them. Export `PI_INTERCOM_STABLE_ID` per shell when one session needs a restart-stable id.

## Trust

The broker binds a local socket only. There is no network path, and messaging is same-machine. Any session that loads the extension can address any other, so treat a message from a peer as operator input of the same trust level, never as an authority to skip a gate.

After install, `/reload` or start a new session.
