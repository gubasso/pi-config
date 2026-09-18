"""The engine behind `just deploy`, `just doctor`, and `just status`.

The repo is the state of the live agent directory, not a floor under it, so
this package lands what the repository declares and removes what it stopped
declaring. Most of it is about the second half being safe.

Modules import downward only, and tests/meta/test_architecture.py is what
says so:

    paths  fsx  gitx          nothing in-package
    pins  manifest            the row above
    sidecars  prune  status   the two rows above
    landing  trees            the three rows above
    __main__                  the command line

Every name below is re-exported so a caller can say `pi_config.converge`
without knowing which module grew it. The module is still where the reading
happens.
"""

from __future__ import annotations

from .fsx import (
    copy_regular,
    hardlink_supported,
    prove_nofollow_regular,
    read_bytes,
    replace_with_hardlink,
    same_inode,
    store_owned,
    write_bytes,
)
from .gitx import (
    git_head_bytes,
    git_ignored,
    git_tracked,
)
from .landing import (
    land_atomic_sot,
    land_sidecars,
    prove_sidecars_landing,
    prove_sidecars_source,
)
from .manifest import (
    MANIFEST_NAME,
    MANIFEST_VERSION,
    manifest_path,
    manifest_source,
    prove_manifest,
    read_manifest,
    read_run_manifest,
    record,
    record_new_dirs,
    write_manifest,
    write_manifest_bytes,
)
from .paths import (
    AGENT_PREFIX,
    HOME_MIRROR,
    LANDING_ROOT,
    agent_payload_dir,
    entry_path,
    landing_roots,
    plugin_docs_dir,
    plugins_root,
    relpath_ok,
    sidecar_dest_path,
    sidecar_repo_path,
    sidecar_source_path,
    within_root,
)
from .pins import (
    classify,
    frozen_ref,
    load_pins,
    note_frozen,
    npm_name,
    parse_git,
    plugin_name,
    prove_docs,
    source_of,
)
from .prune import (
    PRUNE_VETO_NAMES,
    RUNTIME_OWNED_DIRS,
    RUNTIME_OWNED_NAMES,
    classify_stale,
    converge,
    live_only_dests,
    prune_mode,
    runtime_owned,
    unmanaged_paths,
)
from .sidecars import (
    SIDECAR_CLASSES,
    SIDECAR_KEYS,
    load_plugin_sidecars,
    load_sidecars,
    prove_json_sidecar,
)
from .status import (
    print_status,
)
from .trees import (
    converge_trees,
    installed_git,
    installed_npm,
    note_trees,
    pi_remove,
)

__all__ = [
    "AGENT_PREFIX",
    "HOME_MIRROR",
    "LANDING_ROOT",
    "MANIFEST_NAME",
    "MANIFEST_VERSION",
    "PRUNE_VETO_NAMES",
    "RUNTIME_OWNED_DIRS",
    "RUNTIME_OWNED_NAMES",
    "SIDECAR_CLASSES",
    "SIDECAR_KEYS",
    "agent_payload_dir",
    "classify",
    "classify_stale",
    "converge",
    "converge_trees",
    "copy_regular",
    "entry_path",
    "frozen_ref",
    "git_head_bytes",
    "git_ignored",
    "git_tracked",
    "hardlink_supported",
    "installed_git",
    "installed_npm",
    "land_atomic_sot",
    "land_sidecars",
    "landing_roots",
    "live_only_dests",
    "load_pins",
    "load_plugin_sidecars",
    "load_sidecars",
    "manifest_path",
    "manifest_source",
    "note_frozen",
    "note_trees",
    "npm_name",
    "parse_git",
    "pi_remove",
    "plugin_docs_dir",
    "plugin_name",
    "plugins_root",
    "print_status",
    "prove_docs",
    "prove_json_sidecar",
    "prove_manifest",
    "prove_nofollow_regular",
    "prove_sidecars_landing",
    "prove_sidecars_source",
    "prune_mode",
    "read_bytes",
    "read_manifest",
    "read_run_manifest",
    "record",
    "record_new_dirs",
    "relpath_ok",
    "replace_with_hardlink",
    "runtime_owned",
    "same_inode",
    "sidecar_dest_path",
    "sidecar_repo_path",
    "sidecar_source_path",
    "source_of",
    "store_owned",
    "unmanaged_paths",
    "within_root",
    "write_bytes",
    "write_manifest",
    "write_manifest_bytes",
]
