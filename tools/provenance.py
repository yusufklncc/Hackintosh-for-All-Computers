"""Where every answer this repository gives comes from.

Four kinds of source, and the difference between them is the difference between
a fact and an opinion:

  derived   read out of a machine-readable file the upstream project ships -
            a kext's Info.plist, a guide's own HTML table. Regenerating it after
            an update produces a diff, so drift is visible rather than silent.
  quoted    the rule exists only in prose, so the table carries the sentence it
            rests on and names where it came from. A human wrote the row; the
            source says whether they were right.
  measured  produced by running something and recording what happened, not by
            asserting what should happen.
  reported  somebody ran macOS on the hardware and wrote down what happened.
            Weaker than a document, and labelled as such wherever it is used,
            but a machine that has been booted beats a table that has never
            heard of it. Each entry names who observed it and what exactly.
  none      no source, so no verdict. The tools say `unknown` here, and will
            keep saying it until there is something to base an answer on.

    python3 tools/provenance.py
    python3 tools/provenance.py --gaps     # only what is not covered

Standard library only, no network. The counts come from the files themselves,
so this cannot claim coverage the repository does not have.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen
import ui

BOLD, DIM, GREEN, YELLOW, RESET = ui.colours('bold', 'dim', 'green', 'yellow', 'reset')

DERIVED, QUOTED, MEASURED, REPORTED, NONE = (
    'derived', 'quoted', 'measured', 'reported', 'none')
KIND_COLOUR = {DERIVED: GREEN, QUOTED: GREEN, MEASURED: GREEN,
               REPORTED: YELLOW, NONE: YELLOW}


def rows_in(path, key):
    if not Path(path).exists():
        return 0
    return len(ocgen.read_toml(path).get(key, []))


def ids_in(path, key='driver', role=None):
    if not Path(path).exists():
        return 0
    total = 0
    for d in ocgen.read_toml(path).get(key, []):
        if role and d.get('role') != role:
            continue
        total += len(d.get('ids', []))
    return total


# What each category rests on. The counts are read; everything else is the
# provenance of the file, which has to be stated somewhere and is stated here.
def catalogue():
    return [
        dict(area='CPU generation', kind=DERIVED, file='profiles/cpu/',
             source='the profile tree itself',
             tool='tools/build.py --list',
             # a name with a second dot is a per-core override, not a profile
             count=f'{len([x for x in Path("profiles/cpu").rglob("*.toml") if "." not in x.stem])} '
                   f'CPU profiles in {len(list(Path("profiles/cpu").iterdir()))} platforms',
             covers='Sandy Bridge to Raptor Lake on Intel, Bulldozer and Ryzen on AMD',
             gap='Laptop profiles are Intel only. Nehalem and older, Core Ultra, '
                 'and Xeon decode to nothing rather than to a guess.'),
        dict(area='A Mac\'s own devices', kind=MEASURED, file='tools/detect.py',
             source="the machine's IORegistry, read while it is running macOS",
             tool='tools/detect.py --report',
             count='6 name fragments, plus whichever driver is attached',
             covers='what each device is and which macOS driver has it, on a '
                    'Mac where no kext claims anything and the running system '
                    'is the only thing that can say',
             gap='Only names that have been seen on a real machine are listed. '
                 'A Mac that calls its Wi-Fi something else gets no role, '
                 'which reads as "nothing recognised" rather than as a guess.'),
        dict(area='Device names', kind=QUOTED, file='data/deviceids.toml',
             source='the PCI ID Project, and hwdata for the USB list',
             tool='tools/deviceids.py --refresh',
             count=f'{rows_in("data/deviceids.toml", "device")} named, '
                   f'{len(ocgen.read_toml(Path("data/deviceids.toml")).get("unnamed", [])) if Path("data/deviceids.toml").exists() else 0} not',
             covers='what to call each id this repository already drives, and '
                    'which vendor made it, so a catalogue can be read and filtered',
             gap='Names only. An id the upstream lists do not carry keeps its '
                 'id as its name - the kext still matches it. USB names come '
                 'from hwdata rather than linux-usb.org, whose file states no '
                 'licence at all.'),
        dict(area='Mac support', kind=DERIVED, file='data/mac.toml',
             source="Apple's own device metadata at gdmf.apple.com/v2/pmv",
             tool='tools/mactable.py --refresh',
             count=f'{rows_in("data/mac.toml", "mac")} machines across '
                   f'{len(ocgen.read_toml(Path("data/mac.toml"))["lines"]) if Path("data/mac.toml").exists() else 0} '
                   f'macOS lines',
             covers='which macOS a real Mac still runs, by the board name it '
                    'reports of itself, Intel and Apple silicon alike',
             gap='Only the lines Apple still serves. A Mac that stopped at '
                 'Monterey reads as "12 and newer" because 11 is as far back '
                 'as the endpoint goes - the floor is the oldest served '
                 'release, not the one the machine shipped with.'),
        dict(area='AMD graphics', kind=DERIVED, file='data/gpu.toml',
             source='dortania.github.io/GPU-Buyers-Guide, parsed from its tables',
             tool='tools/gputable.py',
             count=f'{rows_in("data/gpu.toml", "card")} cards',
             covers='Polaris, Vega, Navi 10/21/23, per card, with boot arguments',
             gap='Cards the guide does not list are unknown, not unsupported.'),
        dict(area='NVIDIA families', kind=DERIVED, file='data/gpu.toml',
             source="the guide's NVIDIA page, which states each family's "
                    'oldest and newest macOS on its own lines',
             tool='tools/gputable.py',
             count=f'{rows_in("data/gpu.toml", "nvidia")} families',
             covers='every NVIDIA card, by the chip codename the PCI ID '
                    'Project puts in its name: GK is Kepler and ends at Big '
                    'Sur, GP is Pascal and ends at High Sierra, TU and newer '
                    'never had a driver',
             gap='A card the id list has no name for gets no family and falls '
                 'back to the whole-vendor rule. The rebranded-Fermi section '
                 'speaks for three named chips only, so a real Fermi is '
                 'unclaimed rather than mislabelled.'),
        dict(area='NVIDIA and Arc', kind=QUOTED, file='data/gpu.toml',
             source='the same guide, which states these by family in prose',
             tool='tools/gputable.py',
             count=f'{rows_in("data/gpu.toml", "family")} family rules',
             covers='the fallback when no family claims a card, and every '
                    'Intel Arc',
             gap='A whole-vendor sentence. It is now the last resort rather '
                 'than the only answer - see NVIDIA families above.'),
        dict(area='Intel iGPU', kind=DERIVED, file='data/gpu.toml',
             source='the same guide, per generation, with its framebuffer ids',
             tool='tools/gputable.py',
             count=f'{rows_in("data/gpu.toml", "igpu")} generation sections',
             covers='Ivy Bridge to Raptor Lake, and which one to start with',
             gap='Rocket Lake and newer have no supported iGPU, so no ids.'),
        dict(area='Framebuffer ids', kind=DERIVED, file='data/framebuffer.toml',
             source="WhateverGreen's own tables, at the tag matching the kext",
             tool='tools/fbtable.py',
             count=f'{rows_in("data/framebuffer.toml", "framebuffer")} framebuffers, '
                   f'{rows_in("data/framebuffer.toml", "native")} native ids, '
                   f'{rows_in("data/framebuffer.toml", "support")} macOS ranges',
             covers='Ivy Bridge to Ice Lake: type, connectors, memory, which '
                    'device ids need no faked device-id, and the macOS range '
                    'each generation states',
             gap='Sandy Bridge has a section but no list in that form. '
                 'Connector patches are per machine and are not written at all.'),
        dict(area='Audio codecs', kind=DERIVED, file='data/audio.toml',
             source="AppleALC's own Resources/<CODEC>/Info.plist, pinned release",
             tool='tools/audiotable.py',
             count=f'{rows_in("data/audio.toml", "audio")} codecs',
             covers='every layout AppleALC ships, with the machine each names',
             gap='Which layout works is still a list to try, not an answer.'),
        dict(area='Network and trackpad devices', kind=DERIVED, file='data/hardware.toml',
             source="each kext's own Info.plist match keys",
             tool='tools/hwtable.py',
             count=f'{ids_in("data/hardware.toml")} device ids across '
                   f'{rows_in("data/hardware.toml", "driver")} entries',
             covers='Ethernet, Wi-Fi, Bluetooth and I2C controllers, PCI, USB and ACPI',
             gap='Only the kexts this repository vendors. A device no vendored '
                 'kext claims is unknown.'),
        dict(area='Which kext on which macOS', kind=QUOTED, file='data/network.toml',
             source="each project's own README, quoted per rule",
             tool='hand written, one source line per set',
             count=f'{rows_in("data/network.toml", "set")} sets, '
                   f'{rows_in("data/network.toml", "variant_set")} per-release set',
             covers='Darwin bounds for every network and storage kext added',
             gap='A project that states no bound gets none.'),
        dict(area='Trackpad bus rules', kind=QUOTED, file='data/input.toml',
             source='VoodooI2C, VoodooRMI, VoodooSMBus and Dortania, quoted',
             tool='hand written',
             count=f'{rows_in("data/input.toml", "rule")} rules',
             covers='I2C, Synaptics SMBus, ELAN SMBus, and the PS/2 keyboard rule',
             gap='I2C is read from the controller ids and SMBus from what '
                 'Windows named the bus; a Linux or macOS report has neither.'),
        dict(area='macOS releases', kind=DERIVED, file='data/macos.toml',
             source="the repository's own patch comments, cross-checked",
             tool='tools/coverage.py --names',
             count=f'{rows_in("data/macos.toml", "release")} releases',
             covers='release name to Darwin major, which is what OpenCore bounds on',
             gap='A release newer than the table has to be added by hand.'),
        dict(area='OpenCore versions', kind=MEASURED, file='profiles/support.toml',
             source='every profile validated against every release, recorded',
             tool='tools/matrix.py',
             count='0.8.7 to 1.0.7',
             covers='the range actually observed to validate, not a claim',
             gap='Never regenerated by extract.py, so it stays a measurement.'),
        dict(area='Published configs', kind=MEASURED, file='profiles/catalogue.toml',
             source='sha256 of each config the profiles produce',
             tool='tools/verify.py',
             count=f'{rows_in("profiles/catalogue.toml", "config")} configs',
             covers='byte equality between generated and published',
             gap='None. This is the gate.'),
        dict(area='Field reports', kind=REPORTED, file='data/field.toml',
             source='running macOS on the machine, attributed per entry',
             tool='hand written',
             count=f'{rows_in("data/field.toml", "igpu")} iGPU exception{"s" if rows_in("data/field.toml", "igpu") != 1 else ""}',
             covers='processors whose iGPU behaves differently from its generation',
             gap='One person, one machine each. It outranks the generation rule '
                 'because it is more specific, not because it is stronger.'),
        dict(area='Kext load order', kind=DERIVED, file='EFI/OC/Kexts/',
             source="OSBundleLibraries in each kext, as OpenCore's manual says",
             tool='tools/kextorder.py',
             count='28 of 54 bundles declare a dependency',
             covers='that every kext is listed after the ones it needs, in every '
                    'published config and every build',
             gap='Only kexts vendored here. It reports and never reorders: the '
                 'order is a decision, and rewriting it would hide the mistake.'),
        dict(area='Third-party licences', kind=DERIVED, file='vendor/licences.toml',
             source="each project's own LICENSE file, read from GitHub",
             tool='tools/thirdparty.py --refresh',
             count=f'{rows_in("vendor/licences.toml", "upstream")} upstream projects',
             covers='what every vendored kext is under, including the ones under '
                    'nothing',
             gap='Five projects state no licence at all. The report makes that '
                 'visible; it does not resolve it.'),
        dict(area='Drivers not shipped', kind=DERIVED, file='data/candidates.toml',
             source='each project checked to exist, ids read from its own release',
             tool='tools/thirdparty.py --fetch',
             count=f'{rows_in("data/candidates.toml", "candidate")} candidates',
             covers='what vendoring each one would add, counted from the kext',
             gap='Not a recommendation. Two are archived with no release, and '
                 'three state no licence.'),
        dict(area='Camera', kind=NONE, file='-',
             source='none', tool='-',
             count='bus only',
             covers='whether it is on USB, which is the one thing that decides itself',
             gap='No table of which sensors work. Nothing is claimed beyond the bus.'),
        dict(area='Card reader', kind=DERIVED, file='data/cardreader.toml',
             source="0xFireWolf/RealtekCardReader's own device table",
             tool='tools/cardtable.py',
             count=f'{rows_in("data/cardreader.toml", "device")} Realtek readers',
             covers='which Realtek readers that driver drives, and which it lists '
                    'and does not',
             gap='Realtek only, and the kext is not shipped here - the row says so. '
                 'The project calls itself pre-1.0 beta and last moved in 2022.'),
        dict(area='ACPI and SSDTs', kind=DERIVED, file='vendor/tools.lock',
             source='SSDTTime, vendored whole and driven',
             tool='tools/acpi.py',
             count='SSDTTime and 5 compilers, pinned by hash',
             covers='the SSDTs the tool writes against a machine\'s own tables, '
                    'and the patches it writes with them',
             gap='Nothing here decides which patches a machine needs: six run '
                 'unattended because they decide from the tables, the rest ask. '
                 'Dumping tables needs Windows or Linux.'),
        dict(area='USB port mapping', kind=DERIVED, file='vendor/tools.lock',
             source='USBToolBox, vendored whole and driven',
             tool='tools/usbmap.py',
             count='1 tool, pinned by hash',
             covers='the map the tool writes, on Windows, run from the builder',
             gap='Windows only, because that is the build the project publishes. '
                 'Nothing here can produce a map without a person at the machine.'),
        dict(area='AMD graphics kexts', kind=NONE, file='-',
             source='out of scope by request', tool='-',
             count='-', covers='-',
             gap='NootedRed and NootRX are excluded deliberately.'),
    ]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--gaps', action='store_true', help='only what is not covered')
    a = ap.parse_args(argv)

    table = catalogue()
    if not a.gaps:
        print(f'{BOLD}Where the answers come from{RESET}\n')
        width = max(len(r['area']) for r in table)
        for r in table:
            colour = KIND_COLOUR[r['kind']]
            print(f'  {r["area"]:<{width}s}  {colour}{r["kind"]:<9s}{RESET} '
                  f'{r["count"]:<28s} {DIM}{r["file"]}{RESET}')
        counts = {k: sum(1 for r in table if r['kind'] == k)
                  for k in (DERIVED, QUOTED, MEASURED, REPORTED, NONE)}
        print(f'\n  {counts[DERIVED]} derived from a machine-readable source, '
              f'{counts[QUOTED]} quoted from prose, {counts[MEASURED]} measured, '
              f'{counts[REPORTED]} reported from running it, '
              f'{counts[NONE]} with no source.')
        print(f'  {DIM}The last group is why some rows say unknown. That is the '
              f'honest answer, not a missing feature.{RESET}\n')

    print(f'{BOLD}What each one does not cover{RESET}\n')
    for r in table:
        print(f'  {BOLD}{r["area"]}{RESET}  {DIM}{r["source"]}{RESET}')
        if r['covers'] != '-':
            print(f'      covers   {r["covers"]}')
        print(f'      {YELLOW}gap{RESET}      {r["gap"]}')
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
