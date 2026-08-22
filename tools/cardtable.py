"""Build data/cardreader.toml from RealtekCardReader's own device table.

macOS has no driver for a Realtek card reader, and until now this repository had
nothing to say about one beyond "there is one". There is a driver, and it
publishes a table: device id, name, whether it is supported, and the version it
started working in - which is exactly the shape data/hardware.toml has, so it is
parsed rather than retyped.

The project also states which macOS releases it has been tried on, in a sentence,
and says plainly that others have not been. That sentence is carried too: a
driver's own account of where it has been tested is worth more than a range
somebody inferred.

    python3 tools/cardtable.py
    python3 tools/cardtable.py --from README.md
"""
import argparse
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

REPO = '0xFireWolf/RealtekCardReader'
DOC = 'README.md'
KEXT = 'RealtekCardReader.kext'

ROW = re.compile(
    r'^\|\s*(?P<series>[\w]+)\s*\|\s*0x(?P<vendor>[0-9A-Fa-f]{4})(?P<device>[0-9A-Fa-f]{4})\s*'
    r'\|\s*(?P<name>[^|]+?)\s*\|\s*(?P<supported>Yes|No|Not Yet)\s*\|\s*(?P<since>[^|]+?)\s*\|',
    re.M)
SYSTEMS = re.compile(r'^## Supported Systems\s*\n(?P<body>(?:^-[^\n]*\n)+)', re.M)


def fetch(ref):
    url = f'https://raw.githubusercontent.com/{REPO}/{ref}/{DOC}'
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode('utf-8')


def parse(text):
    """(devices, the systems sentence) from the project's own README."""
    devices = []
    for m in ROW.finditer(text):
        devices.append({
            'id': f'{m.group("vendor").lower()}:{m.group("device").lower()}',
            'name': m.group('name').strip(),
            'series': m.group('series'),
            # "Not Yet" is the project's own wording for a device it knows about
            # and does not drive. That is a different answer from silence.
            'supported': m.group('supported') == 'Yes',
            'since': m.group('since').strip(),
        })
    m = SYSTEMS.search(text)
    systems = [l.strip('- ').strip() for l in m.group('body').splitlines()] if m else []
    return devices, systems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default='data/cardreader.toml')
    ap.add_argument('--ref', default='master')
    ap.add_argument('--from', dest='local', help='a copy of the README on disk')
    a = ap.parse_args(argv)

    text = Path(a.local).read_text(encoding='utf-8') if a.local else fetch(a.ref)
    devices, systems = parse(text)
    if not devices or not systems:
        sys.exit('no device table found; the README layout may have changed')

    ocgen.write_toml(Path(a.out), {
        'driver': {'kext': KEXT, 'project': REPO, 'license': 'BSD-3-Clause',
                   'systems': systems,
                   'note': 'the project calls itself Pre-1.0 Beta and says other '
                           'systems are not tested yet'},
        'device': devices,
    }, '# Realtek card readers, from the driver\'s own device table.\n'
       '#\n'
       f'# Parsed by tools/cardtable.py from {REPO}\'s README, which\n'
       '# publishes a device id, a name and whether each one works. macOS\n'
       '# ships no driver for these, so without this the answer for a card\n'
       '# reader was "there is one" and nothing more.\n'
       '#\n'
       '# supported = false is the project saying it knows the device and does\n'
       '# not drive it, which is a different answer from silence.\n'
       f'# Source: https://github.com/{REPO}')
    works = sum(1 for d in devices if d['supported'])
    print(f'  {len(devices)} card readers, {works} driven, {len(devices) - works} not yet')
    print(f'  tested on: {", ".join(systems)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
