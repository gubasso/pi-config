# pi-better-edit

Pin: `npm:pi-better-edit` in source `settings.json` (unversioned; freeze only if asked). Upstream: <https://github.com/Rianico/pi-better-edit> Landing: [SPEC.md](./SPEC.md). Machine: [sidecars.json](./sidecars.json). Selection: [guides/package-selection.md](../../guides/package-selection.md). Install: [guides/install-packages.md](../../guides/install-packages.md).

Hash-anchored `read` and `edit` (content hashes, fail-closed, no fuzzy match). No agent-dir config file. Empty `sidecars` array.

Runtime store is `$XDG_CONFIG_HOME/pi-better-edit/hash-store.sqlite` (else `~/.config/pi-better-edit/hash-store.sqlite`). It is cache, not a sidecar. Each host or project container keeps its own store via that runtime's `HOME` / `XDG_CONFIG_HOME`. Do not bind-mount or sync it.
