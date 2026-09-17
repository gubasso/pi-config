# pi-config clone

This working tree is the **source** of global Pi config, not the live agent directory. Pi reads `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`.

- `just deploy` copies static payloads and `copy` sidecars, and symlinks `settings.json`, `keybindings.json`, and `symlink` sidecars. `just doctor` and `just check` prove the contract.
- Package pins live in `settings.json`. Write `npm:<name>` or `git:host/repo` with no version and no SHA unless the operator explicitly asks to freeze. Findings live in `docs/plugins/<plugin-name>/`.
- This clone is SoT for every plugin config. A pin without a classified `sidecars.json` is unfinished.
- Never commit `auth.json`, live-only sidecars, session transcripts, or install trees.
- Never deploy this override file.

See `SPEC.md`. Package selection: [docs/guides/package-selection.md](docs/guides/package-selection.md). LSP pin: [docs/guides/lsp.md](docs/guides/lsp.md).

## Choosing a plugin

Never choose, keep, or reject a plugin because it fits or does not fit the current sidecar taxonomy, deploy, or live-agent-dir layout. That is not a criterion and must not become one.

The criterion is: the package that makes the model more precise, deterministic, and effective at the job, with token-sane results. Popularity, maturity, usability, and compatibility with the other pins are clues. If a better package needs a refactor or a greenfield landing, do that. Setup cost, refactor cost, and greenfield cost are not selection criteria.

Sidecar classification below is how a chosen package is landed.

## Install or change a plugin

1. Read upstream docs and the installed source. List every config file the package reads under the live agent dir.
2. Classify each file:
   - can hold tokens or mixed secrets → `live-only` (gitignore; dest only; never symlink or copy)
   - no secrets, runtime may write → `symlink` (track here; deploy links dest → source). If the package refuses symlinks (`O_NOFOLLOW` / atomic rename), `copy` plus `followsSymlinks: false` (hardlink + 3-way sync)
   - no secrets, we own the bytes, runtime does not write → `copy`
3. Land `docs/plugins/<plugin-name>/README.md`, `SPEC.md`, and `sidecars.json`. Create the source sidecar for every required `copy` / `symlink` row (`{}` is a managed default).
4. `pi install` the pin. `just deploy`. `just doctor`.
