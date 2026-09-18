// The TypeScript half of the suite. scripts/run-tests.sh is what runs it, and
// a pre-commit hook is what runs that.
//
// Kind is selected by the path the runner passes, so `vitest run tests/unit`
// is the whole mechanism and this file declares no projects. Cost and venue
// come from tests/helpers/tags.ts, which reads PI_TEST_TAGS.
//
// No transform step is configured on purpose. Node strips the types itself,
// tsconfig.json sets `erasableSyntaxOnly`, and the payload extensions must
// keep loading with no build for `just deploy` to stay a copy.

import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],
    environment: "node",
    // A test that reaches the network or a real HOME is a bug in this tree,
    // not a slow test. Fail it rather than wait for it.
    testTimeout: 10_000,
    // The suite is small. One reporter, no coverage provider, nothing to
    // install beyond what package-lock.json already pins.
    reporters: ["default"],
  },
});
