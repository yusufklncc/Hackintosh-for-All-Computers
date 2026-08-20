# Phase 0 - config tree analysis

Historical. Read-only tooling used to decide whether the 178 hand-maintained
configs under `EFI/OC/config/` could be generated from a layered profile set
instead. They can, they now are, and that tree has been removed - so these
scripts only run against a checkout old enough to still have it.

Kept because they are the evidence behind the decision, not just its result.

Run from the repository root, Python 3.11+, no dependencies:

    python3 tools/phase0/classify.py /tmp/configs.json   # path -> layer coordinates
    python3 tools/phase0/delta2.py   /tmp/configs.json   # overlay consistency
    python3 tools/phase0/layers.py   /tmp/configs.json   # key ownership per level

`delta.py` is the strict variant of `delta2.py`: it counts generated identity
fields (serial, MLB, UUID) and `Comment` strings as real differences. Useful to
see the raw picture, misleading as a modelling signal.

Findings are summarised in `FINDINGS.md`.
