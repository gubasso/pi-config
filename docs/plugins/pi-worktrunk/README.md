# pi-worktrunk

Pin: `npm:pi-worktrunk` in source `settings.json`. Upstream: <https://github.com/mavam/pi-worktrunk> Landing: [SPEC.md](./SPEC.md). Machine: [sidecars.json](./sidecars.json). Selection: [guides/package-selection.md](../../guides/package-selection.md). Install: [guides/install-packages.md](../../guides/install-packages.md).

Runs Worktrunk from Pi. `/wt` takes the same arguments as the `wt` CLI, the `worktrunk` tool gives the model the same command tree, and a command that moves to another worktree carries the session to a linked session there. Pi lifecycle events set a branch marker in `wt list`. The package requires the `wt` binary on `PATH` and reads no config file of its own.
