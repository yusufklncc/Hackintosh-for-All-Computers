"""Build data/framebuffer.toml from WhateverGreen's own framebuffer lists.

Dortania's guide gives one or two platform ids per generation - the default and
sometimes a headless one - which is enough to start a machine and not enough to
finish one. WhateverGreen documents the whole set, and does it in a markdown
table with the columns that decide between them: whether the framebuffer is
mobile or desktop, how many connectors it has, and how much memory it wants.

So the table is parsed rather than retyped, from the tag matching the vendored
kext, and the ranking stays where it was: Dortania's labelled recommendation
first, the rest after it in the order the project lists them.

    python3 tools/fbtable.py                       # the tag matching the kext
    python3 tools/fbtable.py --ref master
    python3 tools/fbtable.py --from FAQ.IntelHD.en.md
"""
import argparse
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

REPO = 'acidanthera/WhateverGreen'
DOC = 'Manual/FAQ.IntelHD.en.md'

# The document names each list by the framebuffer kext's codename. These are the
# profile names this repository uses for the same silicon. Sandy Bridge has a
# section but no list in this form, and Rocket Lake onwards has no supported
# iGPU at all, so neither appears here.
CODENAME_PROFILES = {
    'Capri': ['ivy-bridge'],
    'Azul': ['haswell'],
    'BDW': ['broadwell'],
    'SKL': ['sky-lake'],
    'KBL/ABL': ['kaby-lake'],
    'CFL/CML': ['coffe-lake', 'coffe-lake-plus', 'coffee-lake-whiskey-lake',
                'comet-lake'],
    'ICL': ['ice-lake'],
}

LIST = re.compile(r'^\*\*\*(?P<name>.+?) framebuffer list:\*\*\*', re.M)
ROW = re.compile(r'^\|\s*(0x[0-9A-Fa-f]{8})\s*\|\s*(\w+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|',
                 re.M)


def fetch(ref):
    url = f'https://raw.githubusercontent.com/{REPO}/{ref}/{DOC}'
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode('utf-8')


def byte_swapped(value):
    """0x591B0000 as the four bytes DeviceProperties wants: 00001b59."""
    n = int(value, 16)
    return ''.join(f'{(n >> s) & 0xff:02x}' for s in (0, 8, 16, 24))


def parse(text):
    """One entry per framebuffer, in the order the document lists them."""
    out = []
    for m in LIST.finditer(text):
        name = m.group('name').strip()
        profiles = CODENAME_PROFILES.get(name)
        if not profiles:
            continue
        # each list ends where the next heading starts, so the rows after this
        # one belong to it and nothing further
        nxt = LIST.search(text, m.end())
        segment = text[m.end():nxt.start() if nxt else len(text)]
        for value, kind, connectors, stolen in ROW.findall(segment):
            out.append({
                'codename': name,
                'profiles': profiles,
                'value': f'0x{value[2:].upper()}',
                'data': byte_swapped(value),
                'type': kind.lower(),
                'connectors': int(connectors),
                'stolen': stolen.strip(),
            })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', default='data/framebuffer.toml')
    ap.add_argument('--ref', default='1.7.0',
                    help='tag to read; the default matches the vendored kext')
    ap.add_argument('--from', dest='local', help='a copy of the document on disk')
    a = ap.parse_args(argv)

    text = Path(a.local).read_text(encoding='utf-8') if a.local else fetch(a.ref)
    entries = parse(text)
    if not entries:
        sys.exit('no framebuffer lists found; the document layout may have changed')

    ocgen.write_toml(Path(a.out), {'framebuffer': entries},
                     '# Intel framebuffer platform ids, from WhateverGreen.\n'
                     '#\n'
                     '# Parsed by tools/fbtable.py from the project\'s own tables in\n'
                     f'# {DOC}, at the tag matching the vendored kext.\n'
                     '# Dortania names one or two per generation; this is the whole\n'
                     '# set, with what tells them apart: mobile or desktop, how many\n'
                     '# connectors, and how much memory the framebuffer takes.\n'
                     '#\n'
                     '# connectors = 0 is a headless framebuffer - no display output -\n'
                     '# so it is never the one to start with.\n'
                     f'# Source: https://github.com/{REPO}/blob/master/{DOC}')
    print(f'  {len(entries)} framebuffers from {a.ref}')
    for name in CODENAME_PROFILES:
        rows = [e for e in entries if e['codename'] == name]
        if rows:
            mobile = sum(1 for e in rows if e['type'] == 'mobile')
            print(f'      {name:9s} {len(rows):3d}  {mobile} mobile, '
                  f'{len(rows) - mobile} desktop, '
                  f'{sum(1 for e in rows if not e["connectors"])} headless')
    return 0


if __name__ == '__main__':
    sys.exit(main())
