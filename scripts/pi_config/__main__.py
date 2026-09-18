"""The command line. One verb per recipe, and nothing internal.

Every verb here is something an operator runs. The old internal verbs, the
ones the justfile's bash called to hand work back to Python, are gone with
the bash that called them.

No `if __name__ == "__main__"` guard. A package's __main__ module runs only
under `python3 -m pi_config`, and the guard once hid a real failure: a
refactor dropped it, every recipe then loaded the module and exited zero
without doing anything, and only the end-to-end tests noticed.
"""

from __future__ import annotations

import json
import sys

from .check import check
from .deploy import deploy
from .doctor import doctor
from .pins import load_pins
from .sidecars import load_sidecars
from .status import print_status
from .trees import converge_trees

VERBS = ("deploy", "doctor", "check", "status", "emit")


def usage() -> None:
    raise SystemExit(f"usage: python3 -m pi_config {'|'.join(VERBS)} SRC DEST")


def main() -> None:
    if len(sys.argv) != 4:
        usage()
    verb, src, dest = sys.argv[1], sys.argv[2], sys.argv[3]
    if verb not in VERBS:
        usage()

    pins = load_pins(src, dest)

    if verb == "emit":
        for row in pins:
            json.dump(row, sys.stdout)
            sys.stdout.write("\n")
        return

    sidecars = load_sidecars(src, pins)

    if verb == "check":
        check(src, pins, sidecars)
        return

    if verb == "status":
        print_status(src, dest, pins, sidecars)
        return

    if verb == "doctor":
        doctor(src, dest, pins, sidecars)
        return

    # deploy. Landing, then converging files, then proving, then converging
    # install trees. Trees go last because `pi remove` runs npm and can need
    # the network: a failure there leaves the config correct and only an
    # install tree orphaned.
    dest = deploy(src, dest, pins, sidecars)
    doctor(src, dest, pins, sidecars)
    converge_trees(dest, pins)


main()
