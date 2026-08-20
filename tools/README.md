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
    cpu/<x>/<y>.<n>core -> override, when one core count deviates
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

## Offline by default

A clone contains everything a build needs. Nothing here reaches the network
unless asked, because the EFI is usually prepared on a different machine from
the one being installed, and often on one that is not online.

    vendor/opencore/<version>/Sample.plist   pinned template, 51 KB
    vendor/kexts.lock                        sha256 + upstream for every kext
    EFI/OC/Kexts/                            the kexts themselves

`ocvalidate` and `macserial` are deliberately *not* vendored: 4 MB per OpenCore
version, and each only improves a build rather than being required for one. When
they are absent, validation is skipped and identity falls back to a placeholder,
both with a warning.

## Commands

    python3 tools/extract.py --out profiles   # profiles from the current tree
    python3 tools/verify.py  --comments       # equivalence gate
    python3 tools/kexts.py   check            # tree matches vendor/kexts.lock
    python3 tools/kexts.py   outdated         # ask GitHub what is newer (network)
    python3 tools/fetch_oc.py 1.0.5           # cache another OpenCore release (network)

Both `extract` and `verify` take an optional Sample.plist path and otherwise use
the vendored one. `fetch_oc.py` is how you move to a different OpenCore version:
each release carries its own `Sample.plist`, EFI skeleton, `ocvalidate` and
`macserial`, so pinning a version pins all of them together and config schema
changes stop being a manual migration.

`kexts.py outdated` compares `CFBundleShortVersionString` against the upstream
release tag as strings. Some projects number the bundle and the tag differently
- SMCAMDProcessor ships bundle 1.0.1 in release 0.7.2f1 - so treat it as a
prompt to look, not as a verdict.

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

Core counts are a profile parameter, not a profile each. A byte inside a kernel
patch becomes `{cores:02x}`, and a position is templated only where every
variant holds its own core count - anything differing for another reason stays
at the reference value and the variants that disagree get their own override.
The reference is chosen as the variant needing the fewest overrides, so an
outlier stays an outlier instead of becoming the norm its siblings correct.
That turns the 11 AMD configs into `bulldozer-jaguar.toml`,
`ryzen-threadripper.toml` and one `ryzen-threadripper.4core.toml`.

Residuals that carry a whole `Kernel.Add` or `Kernel.Patch` list are expected
rather than wasteful: a list replaces wholesale, so changing one entry restates
the list. `ryzen-threadripper.4core.toml` is large for exactly that reason - two
of its sixteen patches differ. It is also the anomaly made visible, and it
disappears if those two patches are ever reconciled (see below).

## An upstream discrepancy this surfaced

The three `Force cpuid_cores_per_package` patches carry different opcodes across
the AMD tree:

    bulldozer 4/6/8   b8 XX ..    ba XX ..    ba XX .. 90
    ryzen 4           b8 XX ..    ba XX ..    ba XX .. 90
    ryzen 6..64       b8 XX ..    b8 XX ..    b8 XX ..

AMD_Vanilla upstream specifies `b8`, `ba` and `ba .. 90` for the three kernel
ranges, which is what Bulldozer and Ryzen 4-core use. Upstream also carries a
fourth patch for kernel 22.4.0-25.99.99 (macOS 13.3+) that this tree does not
have; its patches stop at MaxKernel 22.99.99.

This has not been changed. It is recorded here so the decision is deliberate.

`phase0/` holds the read-only analysis that established the layer structure.
