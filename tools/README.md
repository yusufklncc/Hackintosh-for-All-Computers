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

    python3 tools/setup.py                                         # guided, start here
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

## The guided path

`setup.py` asks a short series of numbered questions and calls `build.py` with
the answers. Where the running system can say something useful - that this is a
laptop, that the CPU is Kaby Lake, that the board is an HP - it appears beside
the question as `detected` and marks its row in the list.

It is never preselected. Detection can be wrong, and a wrong answer that arrives
already ticked is one nobody rechecks, so the person always types a number.

`detect.py` reads the machine through commands that ship with the OS -
PowerShell CIM on Windows, `lspci` and sysfs on Linux, `system_profiler` and
`sysctl` on macOS - so it needs no dependencies and no admin rights. Run it on
its own to see what it found.

Its CPU rule stays quiet unless it is sure. A four-digit Intel SKU normally
names its generation with the first digit, so 2600K is 2nd generation; Ice Lake
mobile breaks that, and 1065G7 is 10th. 10th generation mobile then covers two
architectures, and the G suffix is what separates Ice Lake from Comet Lake.
Everything outside the rules it knows - Xeon, Pentium, first generation Core,
Core Ultra, Apple silicon - returns nothing rather than a guess.

## What the hardware needs

`advise.py` reads the machine's PCI and USB ids and says which kexts they call
for. `setup.py` prints the same report after it builds.

    python3 tools/advise.py
    python3 tools/advise.py --ids 8086:15b8 --usb-ids 8087:0029

`data/hardware.toml` is generated by `tools/hwtable.py` from the kexts
themselves - 526 device ids read out of each kext's own `IOPCIPrimaryMatch`,
`IOPCIMatch` or `idVendor`/`idProduct`. It therefore records what a driver
actually binds to rather than what a guide remembers, and updating a kext and
regenerating shows in the diff exactly which devices it gained or lost.

There is deliberately no list of unsupported hardware. Maintaining one by hand
means copying model names out of prose and keeping them current, and a stale
entry there would be a confident wrong answer. Instead a device that no kext
claims is reported as exactly that, with a link to Dortania's guide - which
covers both cases honestly, since an unclaimed device may equally be one macOS
supports with no kext at all.

## Adding the network kexts

`setup.py` offers two ways to add what it found, because both are reasonable:

* **every macOS the hardware supports** - each kext goes in with the Darwin
  bounds its own documentation gives, and OpenCore loads whichever applies. One
  EFI that boots any of them.
* **one macOS** - only the kexts whose range covers that release, and the bounds
  are dropped since they no longer carry information.

The bounds come from `data/network.toml`, which quotes the project that
published each rule, because unlike `hardware.toml` this cannot be read out of a
kext - it lives in prose. Broadcom Bluetooth is the clearest case: BrcmPatchRAM
for 10.10 and earlier, BrcmPatchRAM2 for 10.11-10.14, BrcmPatchRAM3 for 10.15
and later, BrcmBluetoothInjector only alongside the third, and BlueToolFixup
from macOS 12 where it takes over.

`data/macos.toml` maps release names to Darwin majors. Six of its rows are
cross-checked by `coverage.py --names`, which recovers the same mapping from
this repository's own patch comments without being told.

### Intel Wi-Fi

`AirportItlwm` is compiled against each macOS release's AirPort interface and
published as a separate 15 MB download, eight of them for v2.3.0. Carrying all
eight would add about 126 MB, and an EFI can only hold one anyway - so it is the
one device that always resolves to a single build:

* the newest, `Sonoma14.4`, is vendored and needs no network
* any other release is fetched once into `.itlwm-cache/` and copied into the
  build from there
* nothing is fetched unless a card that needs it was actually detected

This is also why the every-macOS mode asks which release after all when an Intel
Wi-Fi card is present. It is the honest answer: there is no build that covers
them all.

v2.3.0 publishes nothing for Sequoia or Tahoe. Targeting those, the builder says
so and leaves Wi-Fi out rather than shipping a kext built for a different
release.

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

## USB injection is split by kernel

89 configs inject USB ports. They carry two mechanisms, each bounded to the range
where there is evidence for it:

    USBInjectAll   MinKernel 15.0.0  MaxKernel 16.99.99    El Capitan, Sierra
    USBToolBox
    + UTBDefault   MinKernel 17.0.0                        High Sierra and up

USBInjectAll is RehabMan's, abandoned upstream; the bundle here is a community
fork at 0.8.1 whose origin could not be traced. It matches on the SMBIOS `model`
key and knows 87 Mac models, which covers 86 of the 89 configs - `iMac14,4` is
not among them, so three configs get nothing from it today.

USBToolBox attaches to the controller instead, so it needs no model identifier
and no controller rename, and it is still maintained (1.2.0, June 2025). Its
README says it "supports El Capitan and up, although only Catalina and up have
been tested" - but that line dates from May 2021 and was never revisited. Within
weeks of it being written, issues #2 and #3 were filed and fixed for High Sierra
10.13.6 and Mojave, both confirmed working by the reporters, and the 1.2.0
bundle's `OSBundleLibraries` reflects those fixes: `kpi.iokit 15.0.0`, no
`kpi.bsd` dependency. So High Sierra upward has evidence; El Capitan and Sierra
have none either way, and keep the kext with the field record.

`UTBDefault.kext` is the codeless half, which upstream describes as being "for
use before you map, so that you can have all USB ports working before you map" -
exactly the job a distributable install EFI needs. Neither mechanism patches the
port limit, and neither does this repository: `XhciPortLimit` is false in all 179.

## Continuous validation

`.github/workflows/validate.yml` runs on every push and pull request:

* kexts match `vendor/kexts.lock`
* all 179 configs pass the vendored `ocvalidate`
* the profiles still reproduce all 179 configs
* `extract.py` is deterministic - regenerating produces byte-identical profiles
* a laptop build and an AMD build both come out clean

Because `ocvalidate` and `macserial` are vendored for Linux too, the runner needs
nothing beyond a checkout and Python.

## The Windows executable

Most people preparing an EFI are sitting at the Windows machine they are about
to convert, and that machine has no Python. So the release carries
`HackintoshEFIBuilder.exe`: `tools/pyinstaller.spec` bundles the profiles, the
data files, `EFI/` and `vendor/` into it, and `setup.py` chdirs into the
unpacked bundle at startup. The frozen build therefore runs the same code down
the same paths as a checkout, with no second branch to keep working.

It is built on a Windows runner by `.github/workflows/release.yml`, which then
makes it build an EFI from the bundle alone before the release is published.

`--answers 2,10,3` replays a menu run non-interactively. That is what CI uses,
on both platforms, instead of piping keystrokes.

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
