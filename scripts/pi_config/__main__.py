"""The command line. One mode per verb, dispatched to the module that owns it."""

from __future__ import annotations

import json
import os
import sys

from .landing import (
    land_sidecars,
    prove_sidecars_landing,
    prove_sidecars_source,
)
from .manifest import prove_manifest
from .paths import landing_roots
from .pins import load_pins, prove_docs
from .prune import converge
from .sidecars import load_sidecars
from .status import print_status
from .trees import converge_trees, note_trees


def usage() -> None:
    raise SystemExit(
        "usage: python3 -m pi_config "
        "emit|prove-docs|prove-sidecars|land-sidecars|prove-roots|converge|"
        "converge-trees|prove-manifest|status|note-trees SRC DEST"
    )


def main() -> None:
    if len(sys.argv) != 4:
        usage()
    mode, src, dest = sys.argv[1], sys.argv[2], sys.argv[3]
    pins = load_pins(src, dest)
    if mode == "emit":
        for row in pins:
            json.dump(row, sys.stdout)
            sys.stdout.write("\n")
        return
    if mode == "prove-docs":
        prove_docs(src, pins)
        load_sidecars(src, pins)
        return
    sidecars = load_sidecars(src, pins) if mode != "note-trees" else []
    if mode == "prove-sidecars":
        prove_docs(src, pins)
        prove_sidecars_source(src, sidecars)
        if os.environ.get("DOCTOR_SOURCE_ONLY") == "1":
            return
        if not os.path.isdir(dest):
            print(f"note: dest {dest} does not exist (source-only sidecars)")
            return
        prove_sidecars_landing(src, dest, sidecars)
        return
    if mode == "land-sidecars":
        land_sidecars(src, dest, sidecars)
        return
    if mode == "prove-roots":
        for root in landing_roots(dest):
            print(f"ok  landing root {root}")
        return
    if mode == "converge":
        converge(src, dest, sidecars)
        return
    if mode == "prove-manifest":
        prove_manifest(src, dest)
        return
    if mode == "converge-trees":
        converge_trees(dest, pins)
        return
    if mode == "status":
        print_status(src, dest, pins, sidecars)
        return
    if mode == "note-trees":
        note_trees(pins)
        return
    usage()


# No `if __name__ == "__main__"` guard. A package's __main__ module runs only
# under `python3 -m pi_config`, and the guard hid a real failure once: the
# split that created this file dropped it, every recipe then loaded the module
# and exited zero without doing anything, and only the end-to-end tests
# noticed.
main()
