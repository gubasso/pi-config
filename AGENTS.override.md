# pi-config clone

This working tree is the **source** of global Pi config, not the live
agent directory. Pi reads `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`.

- `just deploy` copies static payloads and symlinks `settings.json`. `just doctor` and `just check` prove the contract.
- Package pins live in `settings.json`. Findings live in `docs/plugins/<plugin-name>/`.
- Never commit `auth.json`, `web-search.json`, session transcripts, or install trees.
- Never deploy this override file.

See `SPEC.md`.
