# narumitw-pi-plan-mode

Pin: `npm:@narumitw/pi-plan-mode` in source `settings.json`. Upstream: <https://github.com/narumiruna/pi-extensions/tree/main/packages/pi-plan-mode> Landing: [SPEC.md](./SPEC.md). Machine: [sidecars.json](./sidecars.json). Install: [guides/install-packages.md](../../guides/install-packages.md).

SoT sidecar is `.pi/agent/pi-plan-mode.json`, landed as a hardlink because the package refuses symlinks. Source holds explicit package defaults. Legacy `.pi/agent/plan-mode.json` is live-only and must not exist here.
