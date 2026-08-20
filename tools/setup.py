"""Interactive EFI builder.

Asks a short series of numbered questions and writes the EFI folder for one
machine. Where the running system can tell us something - that this is a laptop,
that the CPU is Kaby Lake, that the board is an HP - it is shown next to the
question as `detected`. It is never preselected and never chosen automatically:
detection can be wrong, and a wrong answer that arrives already ticked is one
nobody rechecks.

    python3 tools/setup.py

Standard library only, no network.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import advise
import detect
import ocgen

PROFILES = Path('profiles')

CPU_LABELS = {
    'yonah-conroe-penryn-legacy-bios': 'Yonah / Conroe / Penryn, Legacy BIOS',
    'yonah-conroe-penryn-uefi-bios': 'Yonah / Conroe / Penryn, UEFI BIOS',
    'lynnfield-clarkdale-legacy-bios': 'Lynnfield / Clarkdale, Legacy BIOS',
    'lynnfield-clarkdale-uefi-bios': 'Lynnfield / Clarkdale, UEFI BIOS',
    'nehalem-westmere-legacy': 'Nehalem / Westmere, Legacy BIOS',
    'nehalem-westmere-uefi': 'Nehalem / Westmere, UEFI BIOS',
    'clarksfield-arrandale-legacy-bios': 'Clarksfield / Arrandale, Legacy BIOS',
    'clarksfield-arrandale-uefi-bios': 'Clarksfield / Arrandale, UEFI BIOS',
    'sandy-bridge-legacy': 'Sandy Bridge, Legacy BIOS',
    'sandy-bridge-uefi': 'Sandy Bridge, UEFI BIOS',
    'sandy-bridge-legacy-bios': 'Sandy Bridge, Legacy BIOS',
    'sandy-bridge-uefi-bios': 'Sandy Bridge, UEFI BIOS',
    'sandy-bridge-e-ivy-bridge-e': 'Sandy Bridge-E / Ivy Bridge-E',
    'ivy-bridge': 'Ivy Bridge', 'haswell': 'Haswell', 'haswell-e': 'Haswell-E',
    'broadwell': 'Broadwell', 'broadwell-e': 'Broadwell-E', 'sky-lake': 'Skylake',
    'skylake-x-w-cascade-lake-x-w': 'Skylake-X/W / Cascade Lake-X/W',
    'kaby-lake': 'Kaby Lake', 'coffe-lake': 'Coffee Lake',
    'coffe-lake-plus': 'Coffee Lake Plus', 'coffee-lake-whiskey-lake': 'Coffee Lake / Whiskey Lake',
    'comet-lake': 'Comet Lake', 'ice-lake': 'Ice Lake', 'rocket-lake': 'Rocket Lake',
    'alder-lake': 'Alder Lake', 'raptor-lake': 'Raptor Lake',
    'bulldozer-jaguar': 'Bulldozer / Jaguar', 'ryzen-threadripper': 'Ryzen / Threadripper',
}

BOLD, DIM, GREEN, RESET = '\033[1m', '\033[2m', '\033[32m', '\033[0m'
if os.environ.get('NO_COLOR') or not sys.stdout.isatty():
    BOLD = DIM = GREEN = RESET = ''


def ask(step, total, question, options, detected=None, allow_skip=False):
    """One numbered menu. options is [(value, label)]. Returns the chosen value.

    `detected` is shown as a note and marks its row, but the person still types
    a number - the whole point is that the machine's guess is visible and
    overridable in the same glance."""
    # the first question runs before the total is known, since a laptop asks
    # fewer than a desktop; claiming a total there would only be wrong
    counter = f'{step}/{total}' if total else f'{step}'
    print(f'\n{BOLD}[{counter}] {question}{RESET}')
    hint = dict(options).get(detected)
    if hint:
        print(f'      {GREEN}detected: {hint}{RESET}')
    elif detected:
        print(f'      {GREEN}detected: {detected}{RESET}')
    for i, (value, label) in enumerate(options, 1):
        mark = f' {GREEN}<- detected{RESET}' if value == detected else ''
        print(f'      {i:2d}) {label}{mark}')
    if allow_skip:
        print(f'      {len(options) + 1:2d}) none of these')
    while True:
        raw = input('      > ').strip()
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(options):
                return options[n - 1][0]
            if allow_skip and n == len(options) + 1:
                return None
        print(f'      {DIM}enter a number from the list{RESET}')


def available(kind):
    return sorted(p.stem.split('.', 1)[1]
                  for p in PROFILES.glob(f'overlay/{kind}.*.toml'))


def cpu_choices(platform_name):
    out = []
    for p in sorted(PROFILES.glob(f'cpu/{platform_name}/*.toml')):
        if '.' in p.stem:                      # per-core override, not a profile
            continue
        out.append((p.stem, CPU_LABELS.get(p.stem, p.stem)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='build/EFI')
    ap.add_argument('--no-detect', action='store_true',
                    help='skip hardware detection and just ask')
    a = ap.parse_args()

    hw = {} if a.no_detect else detect.probe()
    print(f'{BOLD}OpenCore EFI builder{RESET}')
    if hw.get('cpu'):
        print(f'  {DIM}this machine:{RESET} {hw["cpu"]}'
              + (f', {hw["cores"]} cores' if hw.get('cores') else '')
              + (f', {hw["oem_raw"]}' if hw.get('oem_raw') else ''))
        if hw.get('gpu'):
            print(f'  {DIM}graphics:{RESET}     {", ".join(hw["gpu"][:2])}')
    elif not a.no_detect:
        print(f'  {DIM}could not read this machine; every question is still answerable{RESET}')

    # a laptop never asks for vendor or core count, so the count is worked out
    # rather than fixed: "[2/3]" should mean two of three questions left
    total = 0
    step = [0]

    def nxt():
        step[0] += 1
        return step[0]

    plat = ask(nxt(), total, 'What kind of machine is this?',
               [('desktop', 'Desktop'), ('laptop', 'Laptop')],
               detected=('laptop' if hw.get('laptop') else
                         'desktop' if hw.get('laptop') is False else None))

    total = 3            # laptop: platform, generation, brand
    vendor = None
    if plat == 'desktop':
        det = ('amd' if hw.get('generation') in ('ryzen-threadripper', 'bulldozer-jaguar')
               else 'intel' if hw.get('generation') else None)
        # this answer decides whether a core count is asked for, so like the
        # first question it cannot honestly claim a total yet
        vendor = ask(nxt(), 0, 'Which CPU vendor?',
                     [('intel', 'Intel'), ('amd', 'AMD')], detected=det)
        total = 5 if vendor == 'amd' else 4
    else:
        print(f'\n      {DIM}laptop profiles cover Intel only, so no vendor question{RESET}')

    pname = f'{plat}-{vendor}' if vendor else plat
    choices = cpu_choices(pname)
    if not choices:
        sys.exit(f'no profiles for {pname}')
    gen = hw.get('generation')
    cpu = ask(nxt(), total, 'Which CPU generation?', choices,
              detected=gen if any(v == gen for v, _ in choices) else None)

    cores = None
    if vendor == 'amd':
        opts = [(n, f'{n} cores') for n in (4, 6, 8, 12, 16, 24, 32, 64)]
        cores = ask(nxt(), total, 'How many physical cores?', opts,
                    detected=hw.get('cores') if any(v == hw.get('cores') for v, _ in opts) else None)

    oem = ask(nxt(), total, 'Board or laptop brand?',
              [(o, o.upper().replace('-', ' / ')) for o in available('oem')],
              detected=hw.get('oem'), allow_skip=True)

    row = dict(path='', platform=plat, vendor=vendor, cpu=cpu,
               chipset=None, oem=oem, variant=None, cores=cores)
    if not (PROFILES / 'cpu' / pname / f'{cpu}.toml').exists():
        sys.exit(f'no profile for {cpu}')
    if oem and not (PROFILES / 'overlay' / f'oem.{oem}.toml').exists():
        print(f'\n  {DIM}no {oem} overlay for this combination; using the generic profile{RESET}')
        row['oem'] = None

    cmd = [sys.executable, 'tools/build.py', '--platform', plat, '--cpu', cpu,
           '--out', a.out]
    if vendor:
        cmd += ['--vendor', vendor]
    if cores:
        cmd += ['--cores', str(cores)]
    if row['oem']:
        cmd += ['--oem', row['oem']]

    print(f'\n{BOLD}Building{RESET}')
    print(f'  {DIM}{" ".join(cmd)}{RESET}\n')
    sys.stdout.flush()
    r = subprocess.run(cmd)
    if r.returncode != 0:
        return r.returncode
    if hw.get('pci_ids') or hw.get('usb_ids'):
        print()
        advise.report(hw['pci_ids'], hw['usb_ids'], 'this machine')

    print(f'\n  Copy the {BOLD}EFI{RESET} folder from {BOLD}{a.out}{RESET} to the EFI '
          f'partition of your USB drive.')
    print(f'  {DIM}ROM is still a placeholder - set it to your own MAC address, see the '
          f'README Post Installation section.{RESET}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
