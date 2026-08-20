"""Say which kexts this machine's network hardware needs.

Reads the devices the machine reports, looks them up in data/hardware.toml and
prints what it finds. It only ever reports; adding kexts to a config is a
separate, explicit step.

Where nothing matches, it says so rather than guessing. A device this repository
has no driver for is a fact worth stating plainly - it usually means the card
has to be replaced, and a vague answer there costs somebody a day.

    python3 tools/advise.py
    python3 tools/advise.py --ids 8086:15b8,8086:2723 --usb-ids 8087:0026
"""
import argparse
import collections
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect
import ocgen

TABLE = Path('data/hardware.toml')
ROLE_LABEL = {'ethernet': 'Ethernet', 'wifi': 'Wi-Fi', 'bluetooth': 'Bluetooth'}
GUIDES = {
    'ethernet': 'https://dortania.github.io/Anti-Hackintosh-Buyers-Guide/',
    'wifi': 'https://dortania.github.io/Wireless-Buyers-Guide/',
    'bluetooth': 'https://dortania.github.io/Wireless-Buyers-Guide/',
}

BOLD, DIM, GREEN, YELLOW, RESET = '\033[1m', '\033[2m', '\033[32m', '\033[33m', '\033[0m'
if os.environ.get('NO_COLOR') or not sys.stdout.isatty():
    BOLD = DIM = GREEN = YELLOW = RESET = ''


def load_table():
    if not TABLE.exists():
        sys.exit(f'{TABLE} missing; run tools/hwtable.py')
    index = {}
    for d in ocgen.read_toml(TABLE)['driver']:
        for i in d['ids']:
            index.setdefault((d['bus'], i), []).append(d)
    return index


def report(pci, usb, source):
    """Print what the given devices need. Shared with setup.py."""
    index = load_table()
    hits = collections.defaultdict(list)
    for bus, ids in (('pci', pci), ('usb', usb)):
        for i in ids:
            for d in index.get((bus, i), []):
                hits[d['role']].append((i, d))

    print(f'{BOLD}Network hardware{RESET}  {DIM}from {source}: '
          f'{len(pci)} PCI, {len(usb)} USB devices{RESET}')
    if not pci and not usb:
        print(f'\n  {YELLOW}nothing was readable here.{RESET} On a Hackintosh target run this '
              f'from Windows or Linux;\n  a Mac reports its own hardware, not the machine you '
              f'are building for.')
        return

    for role in ('ethernet', 'wifi', 'bluetooth'):
        print(f'\n  {BOLD}{ROLE_LABEL[role]}{RESET}')
        found = hits.get(role)
        if not found:
            print(f'      {YELLOW}no device here is claimed by any kext this repository '
                  f'knows.{RESET}')
            print(f'      {DIM}That means either the device is supported by macOS with no '
                  f'kext at all,\n      or it is not supported. Check {GUIDES[role]}{RESET}')
            continue
        seen = set()
        for device_id, d in found:
            key = (device_id, d['kext'])
            if key in seen:
                continue
            seen.add(key)
            print(f'      {GREEN}{device_id}{RESET}  needs {BOLD}{d["kext"]}{RESET}'
                  f'  {DIM}{d["label"]}, v{d["version"]}{RESET}')

    if [r for r in hits if len({d['kext'] for _, d in hits[r]}) > 1]:
        print(f'\n  {DIM}Some devices match more than one kext - they target different macOS\n'
              f'  versions. The builder picks per target once that step exists.{RESET}')
    print(f'\n  {DIM}This is a report. Nothing was added to any config.{RESET}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ids', help='comma-separated PCI ids to use instead of probing')
    ap.add_argument('--usb-ids', help='comma-separated USB ids to use instead of probing')
    a = ap.parse_args()

    if a.ids is not None or a.usb_ids is not None:
        pci = [x.strip() for x in (a.ids or '').split(',') if x.strip()]
        usb = [x.strip() for x in (a.usb_ids or '').split(',') if x.strip()]
        source = 'the ids you passed'
    else:
        hw = detect.probe()
        pci, usb, source = hw['pci_ids'], hw['usb_ids'], 'this machine'

    report(pci, usb, source)
    return 0


if __name__ == '__main__':
    sys.exit(main())
