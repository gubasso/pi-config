# pi-model-fallback-alias

Pin: `npm:pi-model-fallback-alias` in source `settings.json`. Upstream: <https://github.com/unrelentingfox/pi-model-fallback-alias> Landing: [SPEC.md](./SPEC.md). Machine: [sidecars.json](./sidecars.json). Selection: [guides/package-selection.md](../../guides/package-selection.md). Install: [guides/install-packages.md](../../guides/install-packages.md).

Registers the ten omp built-in `alias/<role>` models from `model-alias.json`. SoT sidecar is `.pi/agent/model-alias.json`, copied because the package only reads it. Parent default stays `xai/grok-4.6` until a second authenticated model exists to put on a leaf chain.
