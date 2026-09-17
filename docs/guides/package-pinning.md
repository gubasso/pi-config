# Pin form: why this config does not freeze

Which spec string a `packages` entry carries. Which package to pick is [package-selection.md](./package-selection.md). Landing is [install-packages.md](./install-packages.md). Contract: [SPEC.md](../../SPEC.md) §9.

## Decision

Write every pin as the unversioned source. Recorded 2026-09-17.

```text
npm:<name>
git:<host>/<user>/<repo>
```

No `@version`. No `@tag`. No git SHA. A freeze is a later decision about one pin, with a written reason and a written removal condition.

The three git entries that carried a full SHA lost it on the same day: `pi-lsp-client`, `pi-ast-grep`, and `pi-queue-steer`. All three SHAs equalled the upstream default-branch head at that moment, so the change moved no bytes.

## What a freeze costs here

Pi treats any ref as a freeze. `buildGitSource` sets `pinned` from the presence of a ref, so a branch name freezes as hard as a SHA. For npm, only an exact version freezes, and a range does not.

A frozen source disappears from the startup update notice. Pi's update check returns early on a pinned source, so the notice never names it. The notice is the only automatic signal this machine gets, and it only displays. It installs nothing.

So a freeze here does two things at once. It holds the version, and it turns off the one report that a newer version exists.

GitHub has the same gap in another ecosystem. Dependabot raises alerts for actions referenced by semantic version and not for actions pinned to a SHA. The shape of the trap is identical.

## Why the usual advice does not transfer

[OpenSSF Scorecard](https://github.com/ossf/scorecard/blob/main/docs/checks.md) rates unpinned dependencies as a medium risk and tells projects to pin by hash. Read the whole remediation. It prescribes a pair: pin the hash, then run Dependabot or Renovate to move the hash. Its own caveat says that pinning "can inhibit software updates, either because of a security vulnerability or because the pinned version is compromised".

This repository can do the first half only. No bot watches `settings.json`. `just check` proves that each pin owns plugin docs and classified sidecars. It never asks upstream what changed.

A pin with no watcher is the half of the pattern that carries only the cost. The research agrees. A study of pinned Maven dependencies concludes that fresh pinning beats stale pinning, and [Pinning Is Futile](https://arxiv.org/pdf/2502.06662) finds that pinning direct dependencies either raises manual review effort sharply or leaves dependencies out of date.

## What the SHA was doing, and what replaces it

A frozen pin earned its place in two ways. Name both, because the replacement has to cover both.

| The SHA gave us                                      | What carries it now                                                 |
| ---------------------------------------------------- | ------------------------------------------------------------------- |
| A record of which upstream commit the operator read  | The `Verified against upstream <sha>` line in each plugin `SPEC.md` |
| An upgrade that lands as a commit in this repository | A commit that bumps that line after the operator reads the diff     |

The audit record and the install spec are two different facts. The plugin SPEC says what was read. The pin says what to install. Keeping them in one string forced a docs edit for every upgrade, across seven files, which is the friction that produced three pins nobody revisited for a month.

## The update ritual

Run these steps when you decide to take new upstream code. Nothing moves until you do.

1. Note the current SHA from `docs/plugins/<name>/SPEC.md`.
2. Run `pi update --extensions`, or `pi update --extension <source>` for one package.
3. Read what moved:

   ```bash
   git -C "${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}/git/<host>/<user>/<repo>" log --oneline <old-sha>..HEAD
   ```

4. Re-read the source for any config path the diff touches, then re-classify sidecars.
5. Commit the new SHA into the `Verified against upstream` line.

`pi update --extensions` resets a git tree hard and runs `git clean -fdx` inside it. Local edits in the install tree do not survive.

Do not run bare `pi update`. That updates the Pi binary, which Nix owns.

## When to freeze one pin

Freeze to hold back a known-bad upstream. That is the only reason.

Write the reason and the removal condition in the commit message, so the freeze carries its own expiry. The previous freeze had one. [lsp.md](./lsp.md) said to pin a commit "until there is a release", and the condition went unchecked until this decision.

A freeze also hides that pin from the startup notice, so the operator owns the recheck by hand for as long as it lasts.

## What this decision does not claim

- It does not claim that pinning is wrong in general. It is right with a bot, and this machine has no bot.
- It does not claim upstream is trustworthy. `pi update --extensions` runs code nobody read until step 3 of the ritual above.
- It does not weaken [install-packages.md](./install-packages.md). Read the source before you install a third-party unit, and read the diff before you trust an update.

## Revisit triggers

Reopen this decision when one of these happens.

- A bot watches `settings.json` pins and opens a change when upstream moves.
- Pi reports pinned sources in the startup update notice, which removes the visibility cost.
- An upstream this config depends on starts shipping breaking changes on its default branch.
- A package this config depends on suffers a supply-chain compromise.
