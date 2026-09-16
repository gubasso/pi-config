<!--
Payload. just deploy copies this file to the live agent dir AGENTS.md.
Rules for work inside this clone live in AGENTS.override.md, which is
not deployed.
-->

# Global agent context

Placeholder. Machine-wide instructions for every pi session on this account.
Repository-specific rules belong in that repository's own AGENTS.md, which pi
layers on top of this file.

- Prefer the smallest change that answers the request.
- Read before writing; state what was verified and what was assumed.
- Ask before anything hard to reverse or outward-facing.
- Non-secret Pi plugin config is sourced from the pi-config clone, not from files created only under the live agent directory.
- Plugin sidecars that can hold tokens stay live-only, like `auth.json`. Do not copy them into git.
