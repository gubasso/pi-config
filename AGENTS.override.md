# pi-config clone

This working tree is the **source** of global Pi config, not the live agent directory. Pi reads `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`.

- `just deploy` copies static payloads and `copy` sidecars, and symlinks `settings.json`, `keybindings.json`, and `symlink` sidecars. `just doctor` and `just check` prove the contract.
- Package pins live in `settings.json`. Findings live in `docs/plugins/<plugin-name>/`.
- This clone is SoT for every plugin config. A pin without a classified `sidecars.json` is unfinished.
- Never commit `auth.json`, live-only sidecars, session transcripts, or install trees.
- Never deploy this override file.

See `SPEC.md`.

## Install or change a plugin

1. Read upstream docs and the installed source. List every config file the package reads under the live agent dir.
2. Classify each file:
   - can hold tokens or mixed secrets → `live-only` (gitignore; dest only; never symlink or copy)
   - no secrets, runtime may write → `symlink` (track here; deploy links dest → source). If the package refuses symlinks (`O_NOFOLLOW` / atomic rename), `copy` plus `followsSymlinks: false` (hardlink + 3-way sync)
   - no secrets, we own the bytes, runtime does not write → `copy`
3. Land `docs/plugins/<plugin-name>/README.md`, `SPEC.md`, and `sidecars.json`. Create the source sidecar for every required `copy` / `symlink` row (`{}` is a managed default).
4. `pi install` the pin. `just deploy`. `just doctor`.
