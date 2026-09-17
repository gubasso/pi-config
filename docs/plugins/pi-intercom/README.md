# pi-intercom

Pin: `npm:pi-intercom` in source `settings.json`. Upstream: <https://github.com/nicobailon/pi-intercom> Landing: [SPEC.md](./SPEC.md). Machine: [sidecars.json](./sidecars.json). Install: [guides/install-packages.md](../../guides/install-packages.md).

Direct 1:1 messaging between Pi sessions on this machine. A local broker routes a message to the session you name. SoT sidecar is `.pi/agent/intercom/config.json`, copied because the package never writes it. Broker runtime files beside it are live-only and gitignored.

Address a session by its alias. `/alias <name>` sets the Pi session name, and the native footer prints it next to the working directory.
