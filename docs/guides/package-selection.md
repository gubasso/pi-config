# Choosing a Pi package

What to pin. Landing is [install-packages.md](./install-packages.md). Contract: [SPEC.md](../../SPEC.md) §9 and §11.9.

## Criterion

Pick the package that makes the model more precise, deterministic, and effective at the job.

Token-sane results are part of that job: bounded output, no junk tools in every prompt, no dump of a whole index. They are not a reason to pick a weaker primitive.

## Clues, not vetoes

| Clue          | Use it for                                                        |
| ------------- | ----------------------------------------------------------------- |
| Popularity    | A signal that others hit the same bugs first                      |
| Maturity      | Crash handling, tests, a real release, an author who still pushes |
| Usability     | `/reload` works, `/status` exists, config is documented           |
| Compatibility | Tool-name collisions with pins already in `settings.json`         |

A clue can change the order of two packages that do the same job equally well. A clue does not keep a package that does the wrong job.

## Not a criterion

- Fit to the current sidecar taxonomy
- Fit to the live agent dir layout
- How much `just deploy` would have to change
- Setup cost, refactor cost, greenfield cost

If a better package reads config outside `${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}`, extend deploy. Do not reject the package. Do not vendor its source into this git tree.

## Pin form

Write `npm:<name>` or `git:<host>/<repo>` with no version and no git SHA.

Float until the operator explicitly asks to freeze. Then write `npm:<name>@<version>` or `git:<host>/<repo>@<sha-or-tag>`.

Do not freeze because the package owns a critical tool, because a release might break, or because another pin already has a SHA. Existing frozen pins stay until that pin is revisited.

## After the pin is chosen

Then classify sidecars and land them. That work is mandatory. It is not the reason the pin won.
