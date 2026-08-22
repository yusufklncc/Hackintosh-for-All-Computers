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

# A DevID block is either a flat list or grouped under a sub-label, and the
# sub-label is finer than the section: the Coffee Lake section carries CFL and
# CML separately, which are different profiles here.
SUBLABEL_PROFILES = {
    'KBL': ['kaby-lake'],
    'ABL': ['kaby-lake'],          # Amber Lake Y shares the Kaby Lake section
    'CFL': ['coffe-lake', 'coffe-lake-plus', 'coffee-lake-whiskey-lake'],
    'CML': ['comet-lake'],
}

# the Ivy Bridge section writes 'DevIDs :' with a space, and matching
# strictly dropped that whole generation without saying so
NATIVE = re.compile(r'^\*\*\*Native supported DevIDs\s*:\*\*\*', re.M)
SUBLABEL = re.compile(r'^- ([A-Z]{3}):\s*$', re.M)
DEVID = re.compile(r'^\s*-\s+`0x([0-9A-Fa-f]{4})`\s*$', re.M)

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


def parse_native(text):
    """The device ids each generation supports without a faked device-id.

    A generation being supported does not mean every part in it is: the document
    says a faked device-id is what Whiskey Lake and Coffee Lake Refresh need, and
    those are exactly the ids missing from these lists. So this is what turns one
    verdict per generation into one per device."""
    out = []
    sections = [(m.start(), m.group(0)) for m in
                re.finditer(r'^## Intel .*$', text, re.M)]
    for k, (pos, _) in enumerate(sections):
        end = sections[k + 1][0] if k + 1 < len(sections) else len(text)
        seg = text[pos:end]
        m = NATIVE.search(seg)
        if not m:
            continue
        # the section's own codename, taken from its framebuffer list heading
        fb = LIST.search(seg)
        default = CODENAME_PROFILES.get(fb.group('name').strip(), []) if fb else []
        stop = seg.find('***Recommended', m.end())
        block = seg[m.end():stop if stop > 0 else m.end() + 1200]

        # split the block at each sub-label; whatever precedes the first one is
        # a flat list belonging to the section
        marks = [(mm.start(), mm.group(1)) for mm in SUBLABEL.finditer(block)]
        chunks = []
        if not marks:
            chunks.append((None, block))
        else:
            if marks[0][0] > 0:
                chunks.append((None, block[:marks[0][0]]))
            for i, (start, label) in enumerate(marks):
                finish = marks[i + 1][0] if i + 1 < len(marks) else len(block)
                chunks.append((label, block[start:finish]))

        for label, chunk in chunks:
            profiles = SUBLABEL_PROFILES.get(label, default) if label else default
            if not profiles:
                continue
            for did in DEVID.findall(chunk):
                out.append({'label': label or (fb.group('name').strip() if fb else ''),
                            'profiles': profiles,
                            'id': f'8086:{did.lower()}'})
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
    native = parse_native(text)
    if not entries or not native:
        sys.exit('no framebuffer lists found; the document layout may have changed')
    # a generation that has a framebuffer list and no device ids means the
    # document moved something and the parser lost it quietly, which is the one
    # failure mode a table like this cannot afford
    for codename, profiles in CODENAME_PROFILES.items():
        if not any(codename == e['codename'] for e in entries):
            continue
        if not any(set(profiles) & set(n['profiles']) for n in native):
            sys.exit(f'{codename} has framebuffers but no native device ids; '
                     f'the document layout has changed')

    ocgen.write_toml(Path(a.out), {'framebuffer': entries, 'native': native},
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
                     '#\n'
                     '# The native rows are the device ids each generation supports\n'
                     '# without a faked device-id. A generation being supported does\n'
                     '# not mean every part in it is: Whiskey Lake and Coffee Lake\n'
                     '# Refresh are missing from these lists and the document says\n'
                     '# exactly what they need instead.\n'
                     f'# Source: https://github.com/{REPO}/blob/master/{DOC}')
    print(f'  {len(entries)} framebuffers and {len(native)} native device ids '
          f'from {a.ref}')
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
