# 99percentpeople-pi-todo

Pin: `npm:@99percentpeople/pi-todo` in source `settings.json`. Upstream: <https://github.com/99percentpeople/pi-extensions/tree/master/extensions/todo> Landing: [SPEC.md](./SPEC.md). Machine: [sidecars.json](./sidecars.json). Install: [guides/install-packages.md](../../guides/install-packages.md).

Atomic `todo` tool with a read-only widget. SoT sidecar is `99extensions.json` (`todo` namespace), landed as a hardlink because `/99settings` atomically renames onto the path. Source holds explicit package defaults. The file is shared by other `@99percentpeople` packages; this pin owns the sidecar path.
