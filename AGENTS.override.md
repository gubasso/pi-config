# pi-config clone

This working tree is the **source** of global Pi config, not the live
agent directory. Pi reads `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`.

- `just deploy` lands owned files there. `just doctor` and `just check` prove the contract.
- Never commit `auth.json`, session transcripts, or install trees.
- Never deploy this override file.

See `SPEC.md`.
