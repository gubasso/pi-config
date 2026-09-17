---
description: Review the uncommitted changes in the working tree
argument-hint: "[path]"
---

Review the uncommitted changes in ${1:-the working tree}. Start from `git status --short`, then read `git diff` (and `git diff --cached`) for the same scope.

Report, in this order:

1. Correctness defects, each with the concrete input or state that triggers it.
2. Anything the change breaks that the diff does not show.
3. Reuse and simplification opportunities.

Say plainly when a section has nothing to report. Do not edit files unless asked.
