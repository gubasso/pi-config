# pi-ast-grep landing

Verified against upstream `4a7d1beee684d96a6890e5fc55710bb63fecca85` (`src/index.ts`, `src/ast-grep/downloader.ts`, `src/ast-grep/binary-path.ts`, README).

## Pin and tree

| Artifact     | This repo                                                                                                       | Live                                      |
| ------------ | --------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| Pin          | `settings.json` `packages` → `git:github.com/code-yeongyu/pi-ast-grep@4a7d1beee684d96a6890e5fc55710bb63fecca85` | symlink already                           |
| Install tree | no                                                                                                              | `git/github.com/code-yeongyu/pi-ast-grep` |

## Sidecars

None. The package reads no file under the live agent dir and no file under `$HOME/.pi` except what `sg` itself might use at runtime.

`sg` resolution (`src/ast-grep/binary-path.ts`, `downloader.ts`): cache → `@ast-grep/cli` next to the install tree → platform npm package → `PATH` → Homebrew paths → GitHub release download into `$XDG_CACHE_HOME/pi-ast-grep/bin` (or `~/.cache/pi-ast-grep/bin`). `PI_OFFLINE=1` skips the download. This repo does not set `PI_OFFLINE`. The cache is not a sidecar.

`ast_grep_replace` defaults to `dryRun: true`.

## Class

Empty `sidecars` array. Checked; nothing to land.

After install, `/reload` or start a new session.
