# pi-lsp-client

Pin: `git:github.com/code-yeongyu/pi-lsp-client@1c981dfcacc456fe4ce9f4120a2f0250b54d6844` in source `settings.json`. Upstream: <https://github.com/code-yeongyu/pi-lsp-client> Landing: [SPEC.md](./SPEC.md). Machine: [sidecars.json](./sidecars.json). Selection: [guides/lsp.md](../../guides/lsp.md). Install: [guides/install-packages.md](../../guides/install-packages.md).

Semantic LSP tools for the agent: diagnostics, definition, references, symbols, prepare-rename, rename. User config is `~/.pi/lsp-client.json` (`root: pi-home`). Extra servers for JSON, TOML, and Markdown; builtins stay. Language servers come from the pi-config flake PATH. Do not run `/lsp install`.
