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
    python3 tools/setup.py --check                                 # what the hardware means, then stop
    python3 tools/summary.py --machine machine.json                # the same for a report
    python3 tools/setup.py --machine machine.json                  # build for another machine
    python3 tools/detect.py --report machine.json                  # take that machine's report
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

## The framebuffer id

Two sources, because they answer different questions. `data/gpu.toml` carries
Dortania's one or two per generation with a reason attached - `default`,
`recommended`, `Headless` - which says where to start. `data/framebuffer.toml`
is WhateverGreen's whole list, parsed by `tools/fbtable.py` from the project's
own markdown tables at the tag matching the vendored kext, which says what else
exists: 138 framebuffers with type, connector count and stolen memory.

Kaby Lake laptops went from one candidate to fourteen that way. Every id
Dortania names appears in WhateverGreen's list too, which is the check that
neither parser has drifted, and a headless framebuffer is sorted last however it
was spelled.

The same document lists, per generation, the device ids that need no faked
`device-id` - 58 of them - and those turn one verdict per generation into one
per device. Whiskey Lake and Kaby Lake Refresh sit in supported generations and
are absent from those lists, and the document says elsewhere exactly what they
need instead: `fake device-id A53E0000` and `16590000`. So absent from the list
means *not native*, never *unsupported*, and the row says which:

    Intel iGPU, kaby-lake, natively supported
    Intel iGPU, coffee-lake-whiskey-lake, not natively

Ivy Bridge writes its heading `Native supported DevIDs :` with a space, which a
strict match dropped silently - a whole generation missing and nothing to say
so. `fbtable.py` now refuses to write a table where a generation has
framebuffers but no device ids.

The menu offers two things that are not framebuffers. `0x12345678` is an id
nothing claims, so no framebuffer kext attaches and macOS falls back to a
picture with no graphics acceleration - useful for a first boot, and attributed
to this repository's maintainer rather than to any upstream document, because no
upstream document states it. The other leaves the key out entirely, which means
*removing* it: the profiles ship a placeholder, and not writing one would leave
that behind and call it a choice. `null` in a `--device-props` file is how that
is expressed.

## The oldest and newest macOS a machine can run

Each part that bounds macOS contributes a window, and the machine's range is
what is left where they overlap:

    macOS  Yosemite 10.10 to Monterey 12
        Broadcom Wi-Fi sets the oldest, Intel graphics the newest

The floors and ceilings come from what already backs a decision elsewhere:
`data/framebuffer.toml` carries the sentence each iGPU generation states about
itself, parsed from the same document as the framebuffers, and `data/network.toml`
already bounds every kext it adds.

Two distinctions the answer depends on:

* **A set covers wherever any one of its kexts applies.** Broadcom Bluetooth is
  four kexts in a relay with no gap in it, so the set's floor is the oldest kext's,
  not the newest.
* **A kext that only improves a device does not raise the floor.** NVMeFix wants
  10.14 and the drive works without it, so the set is marked `optional` and left
  out of the reckoning. A kext the card cannot work without is not.

An iGPU a field report says does not accelerate bounds nothing either - the
machine is not going to be run on it.

What this cannot see is stated next to it: the SMBIOS a build picks has a ceiling
of its own, and so can a discrete card, and neither is recorded in this repository.

## The card reader

macOS ships no driver for a Realtek card reader, so the answer here used to be
"there is one" and nothing more. There is a driver -
[0xFireWolf/RealtekCardReader](https://github.com/0xFireWolf/RealtekCardReader),
BSD-3 - and it publishes a table with a device id, a name, and whether each one
works. `tools/cardtable.py` parses it, the same way every other id table here is
parsed rather than retyped.

Three answers now, where there was one:

* the driver drives it - `RealtekCardReader.kext since 0.9.3  [10ec:5227]`
* the driver lists it and does not drive it yet - the project's own wording,
  which is a different answer from silence
* no driver here knows it, which is still `unknown`

**The kext is not shipped here**, and the row says so. Vendoring it is a
decision, not a consequence of having the data: the project calls itself pre-1.0
beta and last moved in 2022.

## When somebody has actually run it

`data/field.toml` holds observations that no upstream document carries, and it
is the only table here that rests on nothing but somebody having booted the
machine. Each entry names who observed it and what exactly they saw, and the
tools label the verdict that way rather than presenting it as a documented fact.

The first entry is the i5-10200H: Dortania states iGPU support per generation
and WhateverGreen per device id, and Comet Lake is supported by both, so every
rule here would call that processor's iGPU supported. It installs and the
graphics never accelerate. A single SKU is below the resolution of either
source, so it can only be recorded from having run it.

An entry outranks the generation rule because it is more specific, not because
it is stronger. It earns its place by being specific about the observation:
"does not work" is not an entry, "installs, but graphics acceleration cannot be
made to work" is.

Where one applies, the framebuffer section is skipped entirely and the
placeholder the profiles ship is removed - an id will not rescue an iGPU that
has been run and found not to accelerate, and leaving a value nobody chose is
worse than leaving the key out.

## What somebody else wrote

    python3 tools/thirdparty.py
    python3 tools/thirdparty.py --machine machine.json
    python3 tools/thirdparty.py --refresh   # re-read the licences (network)
    python3 tools/thirdparty.py --fetch     # count what a candidate adds (network)

**What we ship.** Forty-two kexts from nineteen projects, under six licences.
The LICENSE at the root of this repository covers what is written here and says
nothing about a binary somebody else compiled, so `vendor/licences.toml` records
what each project states, read from its own LICENSE file:

    BSD-3-Clause  6      GPL-2.0  4      GPL-3.0  2      Other  2      none stated  5

Copyleft is an obligation, not an error. **Five projects state no licence at
all** - Mieze's three Ethernet drivers, ECEnabler and the USBToolBox kext - and
that is the absence of permission rather than the granting of it. The report
makes it visible; it does not resolve it. Five more kexts have no upstream
recorded in the lock and are named too.

**What we do not ship.** `data/candidates.toml` lists driver projects for
hardware with no answer here. Each was checked to exist and each carries the
licence that would decide whether it could be vendored at all. `--fetch`
downloads the project's own release and counts its device ids with the same
reader that builds `data/hardware.toml`, so the number is the kext's own:

    AppleIGC           none stated    7 new ids     Intel I225/I226 2.5G Ethernet
    AppleIGB           none stated    no release    Intel I211/I350, archived
    RealtekRTL8100     none stated    no release    Realtek Fast Ethernet, archived
    RealtekCardReader  BSD-3-Clause   14 new ids    Realtek SD card readers

Nothing here is a recommendation. The list exists so that "this repository does
not know about your device" can be followed by "and here is who does". That
three of the four state no licence is itself the finding: the coverage we lack
is mostly behind projects that grant nothing.

The existence of several was learnt from `lzhoang2801/OpCore-Simplify`, whose
`pci_data.py` covers roles this repository does not. None of its data is copied;
the ids come from the kexts.

## Where the answers come from

    python3 tools/provenance.py            # every category and its source
    python3 tools/provenance.py --gaps     # only what is not covered

Four kinds of source, and the counts are read off the files rather than typed,
so the report cannot claim coverage the repository does not have:

* **derived** - read out of a machine-readable file the upstream project ships.
  Regenerating after an update produces a diff, so drift is visible.
* **quoted** - the rule exists only in prose, so the row carries the sentence it
  rests on and names where it came from.
* **measured** - produced by running something and recording what happened.
* **none** - no source, so no verdict. This is why some rows say `unknown`, and
  they will keep saying it until there is something to base an answer on.

## What the hardware means

`summary.py` is the screen printed before the first question: one line per part,
with `supported`, `not supported`, `unknown` or `-`.

Every verdict is composed from a table that already backs a decision elsewhere -
`data/gpu.toml` for the cards, AppleALC's layouts for the codec, the device ids
`hwtable.py` reads out of the kexts for the network parts, the profile tree for
the CPU - so the screen cannot claim something the build then contradicts. Where
a table has nothing to say the row is `unknown` and the detail says why. A card
reader gets `unknown` and will keep getting it until there is data to base an
answer on; a verdict invented for it would be worse than the blank.

Nothing on that screen stops a build. It runs before the questions so that an
unsupported Wi-Fi card is known before four answers, not after.

Rows that would be noise are left out rather than filled in: a desktop with no
pointing device gets no trackpad row, and a machine where every row would say
`unknown` gets one line saying so instead of a table saying nothing. That last
case is what a Mac produces - it reports its own hardware, which none of these
tables cover.

Network rows name the card the way the machine named it, not the way the driver
set is labelled: `Intel(R) Dual Band Wireless-AC 3160`, not `Intel Wi-Fi`. The
model is printed beside the id by every source - after the pipe on Windows,
before the bracketed id in `lspci -nn`, after it in `lsusb` - and `detect._names`
keeps it. There is one row per matched device rather than per role, so a machine
with two NICs shows both.

The screen goes above the first question, including the one asking which machine
this is for, so that nothing is answered before it is seen. Answering that
question with a report shows the summary again, for that machine. Ids passed on
the command line are folded in before it renders, so it describes what will
actually be built rather than what was detected.

## Which machine the answers are about

Detection reads the machine the tool runs on, and that is usually not the target:
a USB stick gets made on a computer that already works. So the first question is
whose hardware this is, before anything is shown as `detected`.

    1) This machine
    2) Another machine, and I have its hardware report
    3) Another machine, and I do not have one
    4) Neither - just write this machine's report, to build for it elsewhere

A report is `detect.probe()` written to JSON, which it survives unchanged because
it is only strings, numbers and lists. `write_report` drops the raw `pci` dump
first: nothing downstream reads it, it is large, and it can name a serial number
in a file meant to be handed to someone else. `read_report` returns a complaint
rather than raising, because a report that cannot be used is a reason to fall
back to asking, not a reason to stop - a missing file, a JSON file that is not a
report, or one written by a newer `REPORT_VERSION` than this copy understands.

With a report, every later section - graphics, audio, framebuffer, trackpad,
storage, network - works exactly as it does locally, because they all read the
same dictionary.

Without one, nothing is detected and nothing is guessed. `pick_network()` asks
which Ethernet, Wi-Fi and Bluetooth that machine has by name, listing the sets in
`data/network.toml`, and hands `netkexts.entries()` the same match names that
device matching would have produced. Graphics, audio and the trackpad are not
offered a by-name equivalent: a card name does not carry the framebuffer id or
the codec layout, and inventing one is how a config acquires a value nobody can
trace.

`--no-detect` is the scripting primitive and skips all of it: no detection, no
scope question and no hardware questions, just the profile menus.

A test that detects the machine it runs on is a test whose questions change with
the machine, and `--answers` is positional. A CI runner that happens to have an
NVMe drive gets asked one more question than one that does not, so the same
answer string builds a different EFI on the two - and until `--answers` learned
to say it had run out, it fell through to a closed stdin and failed as an
unexplained flake instead. `tools/fixtures/no-hardware.json` is a report of
nothing; passing it and then `--ids`, `--hda-ids` or `--nvme` puts in exactly the
hardware a test is about and nothing else.

`detect.py` reads the machine through commands that ship with the OS -
PowerShell CIM on Windows, `lspci` and sysfs on Linux, `system_profiler` and
`sysctl` on macOS - so it needs no dependencies and no admin rights. Run it on
its own to see what it found.

Graphics is read from the bus, not from the adapter list. Windows counts every
display adapter as a video controller, including the virtual ones a remote
desktop or dummy-monitor tool installs, and those can outnumber and outrank the
real card - a machine with an Arc B580 reported a virtual driver instead.
Adapters that enumerate under `ROOT` rather than `PCI` are therefore set aside,
and named as ignored rather than dropped quietly, so someone who installed one
can see it was recognised.

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
themselves - 531 device ids read out of each kext's own `IOPCIPrimaryMatch`,
`IOPCIMatch`, `IONameMatch` or `idVendor`/`idProduct`.

A term can carry a mask - `0x9d608086&0xFFFCFFFF` - which makes the low bits of
the device id wildcards, so one term covers 9d60 through 9d63. The mask is
expanded, not read as a second device: doing the latter would have put
`fffc:ffff` in the table. A term loose enough to match more than 256 devices is
a class match rather than a device list and is skipped. Expanding VoodooI2C's
masks reproduces, byte for byte, the 28 ids that used to be written out by hand
in `data/input.toml` - which is why those now come from here instead.

`IONameMatch` carries two shapes. `pci14e4,43a3` is a PCI device, and
`INT33C2` or `AMDI0010` is an ACPI one - a device with no PCI id at all. An I2C
controller on Haswell or Broadwell is enumerated that way, and AMD's only ever
are, so `bus = "acpi"` rows exist alongside `pci` and `usb`.

`IONameMatch` is there because a Lilu plugin has no `IOPCIPrimaryMatch` to read:
it does not bind to the device, it patches the driver that does. AirportBrcmFixup
declares its 21 Broadcom cards as `pci14e4,43a3` names instead, and skipping the
field meant every Broadcom Wi-Fi card came out unrecognised while the Bluetooth
half of the same combo card was found. It therefore records what a driver
actually binds to rather than what a guide remembers, and updating a kext and
regenerating shows in the diff exactly which devices it gained or lost.

There is deliberately no list of unsupported hardware. Maintaining one by hand
means copying model names out of prose and keeping them current, and a stale
entry there would be a confident wrong answer. Instead a device that no kext
claims is reported as exactly that, with a link to Dortania's guide - which
covers both cases honestly, since an unclaimed device may equally be one macOS
supports with no kext at all.

## Graphics

`data/gpu.toml` is built by `tools/gputable.py` from Dortania's GPU Buyers
Guide. The AMD pages state support card by card with the PCI device id beside
each, so those tables are parsed - 59 cards, with the boot argument each family
needs, `agdpmod=pikera` for Navi and `radpg=15` for the older ones. NVIDIA and
Intel state support by family in prose, so those are family rules carrying the
sentence they rest on.

Intel integrated graphics are keyed on the **CPU generation**, not the adapter
name. The guide writes "UHD Graphics for 12th Gen Intel Processors" where
Windows reports "UHD Graphics 770", and bridging that gap by string matching is
how a wrong answer gets stated confidently. Detection already works the
generation out, so it is used instead.

The advice then follows one rule:

* supported card - say so, add the boot arguments its family needs
* unsupported card - say so, and offer the integrated GPU **only if there is one
  and it is itself supported**. Where there is an iGPU whose support could not
  be determined, say that rather than claiming there is no fallback. Name a card
  that would work either way.

`tools/gpu.py` run on its own prints the verdict for a set of worked examples.

## Audio

`data/audio.toml` is read from AppleALC's own `Resources/<CODEC>/Info.plist` by
`tools/audiotable.py`: 110 codecs, 697 layouts, 672 of which name the machine
they were contributed for.

That naming is the useful part. Which layout-id works depends on the machine
rather than the codec, so there is no single answer to give - but a Lenovo can
be told to start with the layout somebody contributed from a Lenovo:

    Realtek ALC255  [10ec:0255]   27 layouts to try
        alcid=28   Realtek ALC255 for Lenovo B470 - vusun123 <- starting with this one

The order is: layouts naming this machine's brand, then layouts naming any
machine, then the rest by id. That is a heuristic about where to start, not a
claim about which is right, which is why every alternative is written to
`NEXT-STEPS.txt` beside the EFI instead of being dropped.

The codec is detected by its own HDA id, which is a device behind the audio
controller and not the controller's PCI id - `HDAUDIO\FUNC_01&VEN_10EC&DEV_0255`
on Windows, `Vendor Id: 0x10ec0255` from ALSA on Linux.

`alcid` is written as a replacement rather than an addition, since most profiles
already ship `alcid=1` and a second one would just be ignored.

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

## Self-test

`tools/selftest.py` asserts what the advice should say - that an unsupported card
offers a supported iGPU but not an unsupported one, that an unknown one is
reported as unknown rather than as absent, that `alcid` replaces the value a
profile ships rather than appending to it.

They live in a file rather than inline in the workflow. They were inline once,
and YAML around a shell around Python is three levels of quoting: one wrong
escape made the whole workflow unparseable, so every run failed in zero seconds
without executing a step. CI now also parses the workflow files as its first
job, so that failure mode announces itself.

## Storage, camera and card reader

NVMeFix is offered when there is a non-Apple NVMe drive and not otherwise. Its
README says it exists to "improve compatibility with non-Apple SSDs" and
"requires at least Lilu 1.4.1 and at least 10.14 system version", so Apple's own
NVMe is the case it is not for and a SATA-only machine gains nothing. The
`MinKernel 18.0.0` comes from that sentence.

Cameras and card readers are reported but nothing is claimed about them. Neither
Dortania's guides nor any other source I could cite states which specific reader
or sensor works, and this is not a place to substitute a guess: the only thing
worth saying is the bus, because a USB camera is handled by the class driver
macOS already has, while one that is not on USB is an IPU or MIPI sensor with no
macOS driver at all.

If you want a verdict for particular readers or sensors, that is knowledge to
write down as data - the same shape as the AMD GPU rules - rather than something
to derive.

## Trackpad

A trackpad does not announce how it is wired, but the controller it hangs off
does. `data/input.toml` takes the 28 Intel I2C controller ids from VoodooI2C's
README, so finding one on the PCI bus is the signal for offering VoodooI2C and
VoodooI2CHID. Nothing decides the trackpad *is* I2C - plenty of machines have
the controller and a PS/2 trackpad - so when a PS/2 device is present too, the
report says so.

The keyboard is left alone. Dortania is blunt about it - *"Most laptop keyboards
are PS2! You will want to grab VoodooPS2 even if you have an I2C, USB, or SMBus
trackpad"* - and the profiles here already decide that per machine, so the line
is repeated as a warning rather than acted on.

`NEXT-STEPS.txt` names the per-family plugins in the same release, the two SMBus
paths for when it is not I2C at all, and the fact that some trackpads need an
SSDT first - which is machine-specific and not something this can write.

## Intel graphics framebuffer

Dortania lists several `AAPL,ig-platform-id` per generation with a reason
attached - default, recommended, headless, "1366x768 screens" - so this is a
short list like the audio layouts, not an answer. The most likely goes in and
the rest are written down. Headless is never the one to start with, since it
means no display output.

67 of the configs in this repository shipped `12345678` for this key, which is a
placeholder rather than a real id, so replacing it is a fix; the replacement is
reported as a warning so it is visible either way.

What this deliberately does not write is framebuffer connector patches. A tuned
laptop config carries twenty more properties - con0/con1 patches, stolenmem,
fbmem - arrived at by trying. Generating those from a guess would look like
configuration and behave like noise.

## USB port map

`--usb-map` takes a `UTBMap.kext` made with the USBToolBox tool, copies it in and
drops `UTBDefault.kext`, which upstream is explicit about: *"it is not needed and
must be removed if you choose to map"*. Producing the map is the tool's job, on
Windows, against the real ports - not something to derive.

## Keeping the tables current

Three of the data files are snapshots of other people's work, and they go stale
quietly - a card gains support, a codec gains a layout, and nothing here would
notice:

| file | source | regenerated by |
|---|---|---|
| `data/gpu.toml` | Dortania's GPU Buyers Guide | `tools/gputable.py` |
| `data/audio.toml` | AppleALC, pinned to a release tag | `tools/audiotable.py` |
| `data/hardware.toml` | the vendored kexts themselves | `tools/hwtable.py` |
| `data/network.toml` | project documentation, in prose | by hand, each rule quoting its source |

`.github/workflows/refresh.yml` runs the first two weekly, and opens a pull
request if anything moved. It never merges: a change there is a change to what
people are told about their own hardware, so the diff is the point.

`hardware.toml` is different - it is checked on every run, because it is
generated from kexts that live in this repository, so it can be held exactly in
step. What that check cannot see is a kext gaining support upstream, so the
refresh run also reports `kexts.py outdated` in the pull request body. Updating
a kext stays a decision rather than something a schedule does.

The generators refuse to write nonsense: `gputable.py` stops if it parses fewer
than 40 cards and `audiotable.py` if it finds fewer than 80 codecs, so a page
being restructured fails the run instead of quietly emptying a table.

`network.toml` cannot be regenerated - which kext to use on which macOS lives in
prose, and its rules carry the sentence they came from so they can be rechecked
by hand.

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

`.github/workflows/windows-exe.yml` builds it and can be run on its own from the
Actions tab, which puts the executable in the run's artifacts - so it can be
tried on a real machine before any tag exists. `release.yml` calls that same
workflow rather than repeating it, so what gets published is the build that was
tested. Either way it has to produce an EFI from its own bundle before the run
is allowed to pass.

`--answers 2,10,3` replays a menu run non-interactively, alongside
`--machine tools/fixtures/no-hardware.json`. That is what CI uses,
on both platforms, instead of piping keystrokes.

Two things the frozen build gets wrong if written the obvious way, both fixed:
a relative script path in the spec resolves against the spec's own directory, so
`tools/setup.py` in a spec that lives in `tools/` looks for `tools/tools/`; and
`sys.executable` is the executable itself rather than an interpreter, so
`setup.py` calls `build.main()` in process instead of spawning it.

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
