# pi-sandbox

Pin: `npm:pi-sandbox@0.8.2` in source `settings.json`. This is a freeze. Upstream: <https://github.com/carderne/pi-sandbox> Landing: [SPEC.md](./SPEC.md). Machine: [sidecars.json](./sidecars.json). Selection: [guides/package-selection.md](../../guides/package-selection.md). Install: [guides/install-packages.md](../../guides/install-packages.md).

The interim guard of every pi session. It wraps each bash command in bubblewrap through `@carderne/sandbox-runtime`, and it checks the built-in `read`, `write`, and `edit` tools against the same allow lists. The policy lives in `home/.pi/agent/sandbox.json`. The guard is partial. The project [README](../../../README.md#the-pi-sandbox-guard) states what it covers and what it does not.

The freeze holds 0.8.2 because the operator audited that release on 2026-11-25. It ends when a wrap of pi in sandbox-runtime (`srt`) lands and this guard retires, or when an audit of a newer release lands.
