# Choosing a Pi package

What to pin. Landing is [install-packages.md](./install-packages.md). Contract: [SPEC.md](../../SPEC.md) §9 and §11.9.

## Criterion

Pick the package that makes the model more precise, deterministic, and effective at the job.

Token-sane results are part of that job: bounded output, no junk tools in every prompt, no dump of a whole index. They are not a reason to pick a weaker primitive.

Read how the package does the job, not what it claims. A step that hands generated code to the model to transcribe, or asks it to re-derive an exact string, is not deterministic. It fails at the moment the operator needs it. Prefer the package that calls its own code path.

## Veto

An archived upstream is a veto. An archived repository takes no fix, however good the code reads today.

```bash
gh api repos/<owner>/<repo> --jq .archived
```

Check the repository the published package points at, not the one a README, a blog post, or a search result names. A package that moved from a standalone repo into a monorepo leaves the old URL behind in old links, and the old repo is often archived while the live one is not. The authoritative pointer is the package itself.

```bash
npm view <pkg> repository.url
```

## Clues, not vetoes

| Clue          | Use it for                                                        |
| ------------- | ----------------------------------------------------------------- |
| Popularity    | A signal that others hit the same bugs first                      |
| Maturity      | Crash handling, tests, a real release, an author who still pushes |
| Usability     | `/reload` works, `/status` exists, config is documented           |
| Compatibility | Tool-name collisions with pins already in `settings.json`         |

A clue can change the order of two packages that do the same job equally well. A clue does not keep a package that does the wrong job.

## Reading the maintenance clue

Stars measure attention. They do not measure whether a bug gets fixed. Read the activity over the last ninety days, and read it for every option before any of them reaches a shortlist.

| Signal               | Query                                                        | What a zero means                       |
| -------------------- | ------------------------------------------------------------ | --------------------------------------- |
| Contributors         | `gh api repos/<r>/contributors --jq length`                  | One author, nobody reviewing their work |
| Issues filed         | `gh api 'search/issues?q=repo:<r>+is:issue+created:><date>'` | Nobody runs it in anger                 |
| Issues closed        | the same query with `closed:>`                               | Reports arrive and die                  |
| Pull requests merged | the same query with `is:pr+merged:>`                         | No outside contribution lands           |

A package whose only issue on record is the one this operator filed has no user base that finds bugs first. This repo is then its QA. That cost belongs in the comparison, next to the feature list.

Stars on a monorepo belong to the whole collection. Do not read them as the package's own.

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
