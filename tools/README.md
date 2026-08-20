# Config generator

The 179 files under `EFI/OC/config/` are highly repetitive: 35 of them differ
from the generic ones by exactly two quirks, and applying a single OpenCore
default to the tree means editing 179 files by hand. These tools replace that
tree with a layered profile set, and prove the replacement is faithful before
anything is removed.

Python 3.11+, standard library only.

## Layers

A config is `Sample.plist` from the pinned OpenCore release, with profiles
merged on top in order:

    base            -> what every config in this repository changes
    platform/<x>    -> desktop-intel | desktop-amd | laptop
    cpu/<x>/<y>     -> one per CPU generation
    overlay/<tag>   -> chipset and OEM deltas (oem.hp is six lines, 35 configs)
    config/<x>      -> per-config exception, when a group is not uniform

Dicts merge key by key. Lists and scalars replace wholesale, because an ordered
list such as `Kernel.Add` is one decision, not a set of independent ones.

`DeviceProperties.Add`, `NVRAM.Add`, `NVRAM.Delete` and `NVRAM.LegacySchema` are
free-form user data rather than schema, so a profile owns each map entirely and
Sample's own entries are cleared before merging.

Serial, MLB, UUID and ROM are never stored in a profile. They are per-machine
identity and get written per build by `macserial`, which is what stops many
installs from sharing one serial.

## Commands

    SAMPLE=$(python3 tools/fetch_oc.py 1.0.5 --what sample)
    python3 tools/extract.py "$SAMPLE" --out profiles   # profiles from the current tree
    python3 tools/verify.py  "$SAMPLE" --comments       # equivalence gate

`fetch_oc.py` downloads and caches an OpenCore release. Each release carries its
own `Sample.plist`, EFI skeleton, `ocvalidate` and `macserial`, so pinning a
version pins all of them together and config schema changes stop being a manual
migration.

## The gate

`verify.py` rebuilds every config from the profiles and compares it against the
file on disk. Identity fields are excluded because a profile never stores them;
`--comments` additionally requires `Comment` strings to match.

    179/179 configs reproduced (Comment strings included)

Nothing under `EFI/OC/config/` may be deleted while that number is short of
179. It is the precondition for the generator replacing the static tree, not a
report about it.

## Known non-minimality

Two things still produce more profile text than necessary. Both are correctness
preserving and scheduled next:

* The 11 AMD core-count profiles differ only in one byte of one kernel patch.
* Combined overlays (`oem.hp/chipset.h77-...`) store the full delta instead of
  composing `oem.hp` with `chipset.h77-...`.

`phase0/` holds the read-only analysis that established the layer structure.
