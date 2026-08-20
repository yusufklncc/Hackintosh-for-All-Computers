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

    base              -> what every config in this repository changes
    platform/<x>      -> desktop-intel | desktop-amd | laptop
    cpu/<x>/<y>       -> one per CPU generation
    overlay/<axis>.<v> -> one per chipset or OEM (oem.hp is six lines, 35 configs)
    overlay/combo/<t> -> residual for one combination, if composing is not enough
    config/<x>        -> residual for one config, if its group is not uniform

Single-axis overlays compose in a fixed order - chipset first, then oem, then
variant - so a vendor firmware workaround wins over a board default. An overlay
is learned only from configs where that axis is the *only* active one, so a
combination can never contaminate it. Whatever composition does not reproduce
becomes a small residual, which is why there is one combo file and six per-config
residuals rather than a file per combination.

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

The comparison is on canonical XML bytes, not on decoded Python values. That
distinction matters: in Python `True == 1 == 1.0`, while `<true/>`,
`<integer>1</integer>` and `<real>1</real>` are three different things to
OpenCore, and an empty `<array/>` is not the same as a missing key. Both trees
are pruned, re-serialised with sorted keys, and compared byte for byte, so those
differences cannot pass.

    179/179 configs reproduced (Comment strings included)

Nothing under `EFI/OC/config/` may be deleted while that number is short of
179. It is the precondition for the generator replacing the static tree, not a
report about it.

## Known non-minimality

One thing still produces more profile text than necessary. It is correctness
preserving:

* The 11 AMD core-count profiles differ only in one byte of one kernel patch.

Residuals that carry a whole `Kernel.Add` list are expected rather than wasteful:
a list replaces wholesale, so enabling one extra kext restates the list.

`phase0/` holds the read-only analysis that established the layer structure.
