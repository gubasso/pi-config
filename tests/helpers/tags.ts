// The cost and venue axes, for vitest.
//
// pytest has markers and bats has file tags. vitest has neither, so this is
// where the same two words get the same two meanings. scripts/run-tests.sh
// sets both variables; running vitest by hand with neither set runs
// everything, which is what you want while debugging.
//
// Usage:
//
//   import { tagged } from "../helpers/tags.ts";
//   test("blocks a mutating git worktree", tagged("fast", ["local", "ci"]), () => { ... });

export type Cost = "fast" | "slow";
export type Venue = "local" | "ci";

const selectedCosts = new Set<string>(
  (process.env.PI_TEST_COST ?? "fast slow").split(/\s+/).filter(Boolean),
);
const selectedVenue = process.env.PI_TEST_VENUE ?? "";

/** Options for a vitest test, skipping it when the run does not select it. */
export function tagged(cost: Cost, venues: Venue[]): { skip: boolean } {
  if (venues.length === 0) {
    throw new Error("a test with no venue never runs; give it local, ci, or both");
  }
  const costWanted = selectedCosts.has(cost);
  const venueWanted = selectedVenue === "" || venues.includes(selectedVenue as Venue);
  return { skip: !(costWanted && venueWanted) };
}
