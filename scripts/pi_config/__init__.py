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
    deploy  doctor            the four rows above
    check                     the five rows above
    __main__                  the command line

Every name below is re-exported so a caller can say `pi_config.converge`
without knowing which module grew it. The module is still where the reading
happens.
"""

from __future__ import annotations

from .check import (
    FORBIDDEN_PATHS,
    FORBIDDEN_PREFIXES,
    check,
    prove_no_tracked_secrets,
    tracked_files,
)
from .deploy import (
    LINKED_FILES,
    PAYLOAD_DIRS,
    PAYLOAD_FILES,
    copy_dir_files,
    copy_file,
    deploy,
    land_payload,
    link_tracked,
    prove_roots,
    refuse_store_symlink,
)
from .doctor import (
    IGNORED_PATHS,
    REQUIRED_IGNORES,
    REQUIRED_META,
    REQUIRED_PAYLOAD,
    doctor,
    fail,
    ok,
    prove_copy,
    prove_dest,
    prove_dest_location,
    prove_link,
    prove_source,
)
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
    landed,
    manifest_path,
    manifest_source,
    prove_manifest,
    read_manifest,
    read_run_manifest,
    record,
    record_new_dirs,
    reset_landed,
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
    describe,
    print_header,
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
    "FORBIDDEN_PATHS",
    "FORBIDDEN_PREFIXES",
    "HOME_MIRROR",
    "IGNORED_PATHS",
    "LANDING_ROOT",
    "LINKED_FILES",
    "MANIFEST_NAME",
    "MANIFEST_VERSION",
    "PAYLOAD_DIRS",
    "PAYLOAD_FILES",
    "PRUNE_VETO_NAMES",
    "REQUIRED_IGNORES",
    "REQUIRED_META",
    "REQUIRED_PAYLOAD",
    "RUNTIME_OWNED_DIRS",
    "RUNTIME_OWNED_NAMES",
    "SIDECAR_CLASSES",
    "SIDECAR_KEYS",
    "agent_payload_dir",
    "check",
    "classify",
    "classify_stale",
    "converge",
    "converge_trees",
    "copy_dir_files",
    "copy_file",
    "copy_regular",
    "deploy",
    "describe",
    "doctor",
    "entry_path",
    "fail",
    "frozen_ref",
    "git_head_bytes",
    "git_ignored",
    "git_tracked",
    "hardlink_supported",
    "installed_git",
    "installed_npm",
    "land_atomic_sot",
    "land_payload",
    "land_sidecars",
    "landed",
    "landing_roots",
    "link_tracked",
    "live_only_dests",
    "load_pins",
    "load_plugin_sidecars",
    "load_sidecars",
    "manifest_path",
    "manifest_source",
    "note_frozen",
    "note_trees",
    "npm_name",
    "ok",
    "parse_git",
    "pi_remove",
    "plugin_docs_dir",
    "plugin_name",
    "plugins_root",
    "print_header",
    "print_status",
    "prove_copy",
    "prove_dest",
    "prove_dest_location",
    "prove_docs",
    "prove_json_sidecar",
    "prove_link",
    "prove_manifest",
    "prove_no_tracked_secrets",
    "prove_nofollow_regular",
    "prove_roots",
    "prove_sidecars_landing",
    "prove_sidecars_source",
    "prove_source",
    "prune_mode",
    "read_bytes",
    "read_manifest",
    "read_run_manifest",
    "record",
    "record_new_dirs",
    "refuse_store_symlink",
    "relpath_ok",
    "replace_with_hardlink",
    "reset_landed",
    "runtime_owned",
    "same_inode",
    "sidecar_dest_path",
    "sidecar_repo_path",
    "sidecar_source_path",
    "source_of",
    "store_owned",
    "tracked_files",
    "unmanaged_paths",
    "within_root",
    "write_bytes",
    "write_manifest",
    "write_manifest_bytes",
]
