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

BOLD, DIM, GREEN, YELLOW, RESET = '\033[1m', '\033[2m', '\033[32m', '\033[33m', '\033[0m'
if os.environ.get('NO_COLOR') or not sys.stdout.isatty():
    BOLD = DIM = GREEN = YELLOW = RESET = ''

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
        dict(area='AMD graphics', kind=DERIVED, file='data/gpu.toml',
             source='dortania.github.io/GPU-Buyers-Guide, parsed from its tables',
             tool='tools/gputable.py',
             count=f'{rows_in("data/gpu.toml", "card")} cards',
             covers='Polaris, Vega, Navi 10/21/23, per card, with boot arguments',
             gap='Cards the guide does not list are unknown, not unsupported.'),
        dict(area='NVIDIA and Arc', kind=QUOTED, file='data/gpu.toml',
             source='the same guide, which states these by family in prose',
             tool='tools/gputable.py',
             count=f'{rows_in("data/gpu.toml", "family")} family rules',
             covers='every card of those vendors, by PCI vendor id',
             gap='No per-card nuance: Kepler is in the note, not in a verdict.'),
        dict(area='Intel iGPU', kind=DERIVED, file='data/gpu.toml',
             source='the same guide, per generation, with its framebuffer ids',
             tool='tools/gputable.py',
             count=f'{rows_in("data/gpu.toml", "igpu")} generation sections',
             covers='Ivy Bridge to Raptor Lake, and which one to start with',
             gap='Rocket Lake and newer have no supported iGPU, so no ids.'),
        dict(area='Framebuffer ids', kind=DERIVED, file='data/framebuffer.toml',
             source="WhateverGreen's own tables, at the tag matching the kext",
             tool='tools/fbtable.py',
             count=f'{rows_in("data/framebuffer.toml", "framebuffer")} framebuffers',
             covers='Ivy Bridge to Ice Lake, with type, connectors and memory',
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
             gap='Nothing readable says which bus a trackpad is on, so only the '
                 'I2C case is acted on and the rest are named in the notes.'),
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
        dict(area='Camera', kind=NONE, file='-',
             source='none', tool='-',
             count='bus only',
             covers='whether it is on USB, which is the one thing that decides itself',
             gap='No table of which sensors work. Nothing is claimed beyond the bus.'),
        dict(area='Card reader', kind=NONE, file='-',
             source='none', tool='-',
             count='detected only',
             covers='that one is present',
             gap='No support data at all. Always reported as unknown.'),
        dict(area='USB port mapping', kind=NONE, file='-',
             source='none', tool='tools/setup.py --usb-map',
             count='-',
             covers='a UTBMap.kext made elsewhere is accepted and replaces UTBDefault',
             gap='The map itself cannot be produced here: it takes plugging a '
                 'device into every port on the machine.'),
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
