# pi-ast-grep

Pin: `git:github.com/code-yeongyu/pi-ast-grep` (unversioned) in source `settings.json`. Upstream: <https://github.com/code-yeongyu/pi-ast-grep> Landing: [SPEC.md](./SPEC.md). Machine: [sidecars.json](./sidecars.json). Selection: [guides/lsp.md](../../guides/lsp.md). Pin form: [guides/package-pinning.md](../../guides/package-pinning.md). Install: [guides/install-packages.md](../../guides/install-packages.md).

AST structural search and rewrite (`ast_grep_search`, `ast_grep_replace` dry-run by default). No agent-dir config file. `sg` is resolved from cache, npm, PATH, Homebrew, then a GitHub download unless `PI_OFFLINE` is set.

The pin is the git source on purpose. `npm:pi-ast-grep` is a different package by a different author, published once as 0.1.0 with no repository field. Never shorten the pin to that name.
