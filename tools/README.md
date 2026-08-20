# Config generator

`EFI/OC/config/` used to hold 179 hand-maintained plists. They were highly
repetitive - 35 of them differed from the generic ones by exactly two quirks -
and applying a single OpenCore default meant editing 179 files by hand. They are
now generated from 62 profiles, and the tree is gone.

`profiles/catalogue.toml` lists all 179 published configs with the hash of each,
so nothing can change what users get without that file changing too.

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

    vendor/opencore/<version>/Sample.plist    pinned config template
    vendor/opencore/<version>/Utilities/      ocvalidate + macserial, all 3 hosts
    vendor/kexts.lock                         sha256 + upstream for every kext
    EFI/                                      kexts, ACPI, drivers, resources

`ocvalidate` and `macserial` are vendored for macOS, Windows and Linux, so a
build validates itself and mints a fresh serial without ever fetching anything.
If a host has no matching binary the build still succeeds: validation is skipped
and identity falls back to a placeholder, each with a warning.

## Commands

    python3 tools/build.py --catalogue                             # published configs
    python3 tools/build.py --name "Laptop/HP/009 - Laptop - Kaby Lake"
    python3 tools/build.py --list                                  # profile axes
    python3 tools/build.py --platform laptop --cpu kaby-lake --oem hp

    python3 tools/verify.py   --comments      # every published config still matches
    python3 tools/release.py  --out dist      # one zip per published config
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

## Building

`build.py` writes an EFI folder holding only what the generated config actually
references - the ACPI tables it lists, the kexts it enables, the drivers it
loads - so the output is one machine's EFI rather than the whole catalogue. A
laptop build comes out around 11 MB against the 18 MB tree.

Identity is minted per build with `macserial`, which is what stops many installs
from sharing one serial. `ROM` is left at its placeholder because it has to be
this machine's primary MAC address and nothing offline can know it; the README's
post-installation section covers setting it.

Every build is checked with the `ocvalidate` matching the OpenCore version it was
built against.

## OpenCore version support

`profiles/support.toml` is measured, not asserted. `tools/matrix.py` builds every
profile against each OpenCore release's own `Sample.plist` and validates it with
that release's own `ocvalidate`:

    OC_CACHE=.oc-cache python3 tools/matrix.py 0.8.7 0.9.0 1.0.0 1.0.5 1.0.7 --write

All 37 profiles validate on every release from **0.8.7 to 1.0.7** - 592 of 592
combinations. The floor is set by `Misc.Boot.HibernateSkipsPicker`, which does
not exist before 0.8.7. No upper bound was found, so `oc_max` is empty.

`extract.py` never rewrites this file, so a range you widen by testing survives
regeneration. `build.py` warns when the requested version falls outside it.

## SecureBootModel stays Disabled

All 179 configs set `Misc.Security.SecureBootModel = Disabled`, against a failsafe
of `Default`. That is correct here, for reasons that are documented rather than
stylistic:

* The OpenCore manual: *"Specifying this value defines which operating systems
  will be bootable. Operating systems shipped before the specified model was
  released will not boot."* Every named model needs at least macOS 10.13.2, and
  `x86legacy` needs 11.0.1. This repository distributes images down to Yosemite.
* *"Starting with macOS 12 SecureBootModel must match the SMBIOS Mac model."*
  101 of the 179 configs use one of 15 pre-T2 SMBIOS models, which have no Apple
  Secure Boot model at all.
* Dortania's Apple Secure Boot page: *"Unsigned and several signed kernel drivers
  cannot be used."* This EFI injects community kexts, and the AMD configs patch
  the kernel.

Because `SecureBootModel` is `Disabled`, `FixupAppleEfiImages` matters. The
manual: that quirk *"is required to load Mac OS X 10.4 to macOS 10.12, and is
required for all newer macOS when SecureBootModel is set to Disabled"* - on
stricter image loaders, a list that explicitly includes OpenDuet, the Legacy BIOS
path this repository supports. It is now `true` in all 179 configs, matching
OpenCore's own `Sample.plist`.

Its Note 3 - pre-processing in memory is incompatible with UEFI Secure Boot -
does not apply here: the BIOS section of the main README already has users turn
UEFI Secure Boot off, on both Intel and AMD.

Enabling it also lowered the OpenCore floor. The key now matches Sample.plist and
so leaves `base.toml` entirely, which is what a version-portable profile set is
supposed to do: the floor moved from 0.9.6 to 0.8.7 without anyone editing a
version number.

## macOS coverage

`tools/coverage.py` reads the `MinKernel`/`MaxKernel` on every enabled kext and
kernel patch and reports where a capability stops being covered. Patches hitting
the same site are treated as one capability, so a patch that hands over to its
successor is not mistaken for a ceiling. Even the Darwin-to-macOS names are
recovered from this tree's own patch comments rather than typed from memory:

    python3 tools/coverage.py
    python3 tools/coverage.py --names

The measured answer: no Intel config has any bounded capability, and since the
AMD profiles took upstream's full patch set, every AMD capability reaches Darwin
**25.99.99**. The one exception is `GenuineIntel to AuthenticAMD`, which upstream
deliberately ends at 20.99.99 because `Bypass GenuineIntel check panic` takes
over above it.

This is also the honest answer to "should there be a `--macos` axis". Measured
against the tree, macOS targeting only ever varied for AMD, and there it was a
stale patch set rather than a profile dimension.

## Continuous validation

`.github/workflows/validate.yml` runs on every push and pull request:

* kexts match `vendor/kexts.lock`
* all 179 configs pass the vendored `ocvalidate`
* the profiles still reproduce all 179 configs
* `extract.py` is deterministic - regenerating produces byte-identical profiles
* a laptop build and an AMD build both come out clean

Because `ocvalidate` and `macserial` are vendored for Linux too, the runner needs
nothing beyond a checkout and Python.

## The gate

`verify.py` rebuilds every published config from the profiles and compares it
against the hash recorded in `profiles/catalogue.toml`. Identity fields are
excluded because a profile never stores them; `--comments` additionally requires
`Comment` strings to match.

While `EFI/OC/config/` still existed, the same command compared against the files
directly, and that is how the profiles were proven faithful before the tree was
removed: 179 of 179, byte for byte, `Comment` strings included.

The comparison is on canonical XML bytes, not on decoded Python values. That
distinction matters: in Python `True == 1 == 1.0`, while `<true/>`,
`<integer>1</integer>` and `<real>1</real>` are three different things to
OpenCore, and an empty `<array/>` is not the same as a missing key. Both trees
are pruned, re-serialised with sorted keys, and compared byte for byte, so those
differences cannot pass.

    179/179 configs reproduced (Comment strings included)

A change to a hash in `catalogue.toml` is a change to what users download. It is
meant to show up in review, so regenerate it deliberately.

## Releases

Every EFI in this repository carries the same binaries; only the `config.plist`
differs, and OpenCore loads nothing the config does not name. So `release.py`
writes two files rather than 179:

    EFI-base.zip    6.4 MB   the EFI folder, everything but OC/config.plist
    configs.zip     0.8 MB   one config.plist per published config

7 MB against the gigabyte that 179 near-identical folders would have cost. A
user extracts the base, copies their `.plist` into `EFI/OC/config.plist`, and
that is the whole assembly. `.github/workflows/release.yml` runs it on a `v*` tag.

`build.py` still produces a single trimmed EFI holding only what one config
references - that is the right shape for one machine, just not for a release.

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

`extract.py` is the migration tool that computed these profiles from the old
tree. It only runs against a checkout that still has one. `phase0/` holds the
read-only analysis that established the layer structure in the first place.
