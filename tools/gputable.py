"""Build data/gpu.toml from Dortania's GPU Buyers Guide.

The AMD pages state support card by card with the PCI device id next to each,
which is exactly what a detected GPU can be looked up by, so those tables are
parsed rather than retyped. NVIDIA and Intel state support by family in prose,
so those rules are written out here with the sentence they came from - there is
nothing to parse and inventing ids for them would be worse than saying "this
family".

    python3 tools/gputable.py --out data/gpu.toml

Needs the network. The result is committed, so a build never does.
"""
import argparse
import html
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

BASE = 'https://dortania.github.io/GPU-Buyers-Guide'
AMD_URL = f'{BASE}/modern-gpus/amd-gpu.html'
INTEL_URL = f'{BASE}/modern-gpus/intel-gpu.html'
NVIDIA_URL = f'{BASE}/modern-gpus/nvidia-gpu.html'

# Dortania marks each card with one of these.
STATUS = {'✅': 'works', '☑️': 'works-spoofed', '⚠️': 'untested',
          '❌': 'unsupported', '❓': 'unknown'}

# Boot arguments the AMD page attaches to a whole family, kept with the family
# heading they appear under.
FAMILY_ARGS = {
    'Navi 23 series': ['agdpmod=pikera'],
    'Navi 21 series': ['agdpmod=pikera'],
    'Navi 10 series': ['agdpmod=pikera'],
    'R7/R9': ['radpg=15'],
    'HD 8000 Series (8xxx)': ['radpg=15'],
    'HD 7000 Series (7xxx)': ['radpg=15'],
}


def fetch(url):
    """The page, however this machine can read it.

    Same fallback the other generators have: urllib carries its own trust
    store and a network that inspects TLS refuses it, while curl uses the
    system's."""
    try:
        with urllib.request.urlopen(url, timeout=40) as r:
            return r.read().decode('utf-8', 'replace')
    except urllib.error.URLError as first:
        import shutil
        import subprocess
        if not shutil.which('curl'):
            raise
        got = subprocess.run(['curl', '-sS', '--max-time', '40', url],
                             capture_output=True, text=True)
        if got.returncode != 0 or not got.stdout.strip():
            raise SystemExit(f'{first}\nand curl: {got.stderr.strip()}')
        return got.stdout


def cells(row):
    return [html.unescape(re.sub(r'<[^>]+>', '', c)).strip()
            for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.S)]


def parse_amd(page):
    """Card rows, each tagged with the family heading above it."""
    out, seen = [], set()
    # h2 groups the cards (Native / Non-Native / Unsupported), h3 names the
    # family a table belongs to and is what the boot arguments hang off
    chunks = re.split(r'<h[23][^>]*>(.*?)</h[23]>', page, flags=re.S)
    family = ''
    for i, chunk in enumerate(chunks):
        if i % 2 == 1:
            family = html.unescape(re.sub(r'<[^>]+>', '', chunk)).strip().lstrip('# ')
            continue
        for table in re.findall(r'<table>(.*?)</table>', chunk, re.S):
            rows = re.findall(r'<tr>(.*?)</tr>', table, re.S)
            if not rows or 'Device ID' not in cells(rows[0]):
                continue
            head = cells(rows[0])
            di, si = head.index('Device ID'), head.index('Status')
            ni = head.index('Notes') if 'Notes' in head else None
            for row in rows[1:]:
                c = cells(row)
                if len(c) <= max(di, si):
                    continue
                ids = re.findall(r'\b([0-9A-Fa-f]{4})\b', c[di])
                mark = next((v for k, v in STATUS.items() if c[si].startswith(k)), None)
                if not ids or not mark:
                    continue
                for did in ids:
                    key = (did.lower(), c[0])
                    if key in seen:
                        continue
                    seen.add(key)
                    e = {'id': f'1002:{did.lower()}', 'name': c[0], 'family': family,
                         'status': mark}
                    if ni is not None and len(c) > ni and c[ni]:
                        e['note'] = c[ni]
                    if FAMILY_ARGS.get(family):
                        e['boot_args'] = FAMILY_ARGS[family]
                    out.append(e)
    return out


# The Intel page splits iGPUs into Native and Unsupported and names the models
# under each. Matching a detected name against those is unreliable - the guide
# writes "UHD Graphics for 12th Gen Intel Processors" where Windows reports
# "UHD Graphics 770" - so the verdict is keyed on the CPU generation, which
# detection already works out, and the model lists are kept for the wording.
IGPU_GENERATIONS = {
    'Ivy Bridge 3XXX': ['ivy-bridge'],
    'Haswell 4XXX': ['haswell'],
    'Broadwell 5XXX': ['broadwell'],
    'Skylake 6XXX': ['sky-lake'],
    'Kaby Lake 7XXX': ['kaby-lake'],
    'Kaby Lake Refresh/Coffee Lake/Coffee Lake Refresh/Whiskey Lake/Comet Lake 8XXX/9XXX/10XXX':
        ['coffe-lake', 'coffe-lake-plus', 'coffee-lake-whiskey-lake', 'comet-lake'],
    'Ice Lake 10XXX': ['ice-lake'],
    'Tiger Lake/Rocket Lake': ['rocket-lake'],
    'Alder Lake/Rocket Lake': ['alder-lake'],
    'Raptor Lake': ['raptor-lake'],
}


def parse_framebuffers(seg):
    """The AAPL,ig-platform-id candidates a generation section lists.

    The page gives each as the value and then its byte-swapped form, which is
    what actually goes into DeviceProperties, plus a label saying why you would
    pick it - "default", "recommended", "1366x768 screens". Both halves are kept:
    the label is the whole reason a list beats a single answer."""
    txt = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', seg)))
    if 'ig-platform-id' not in txt:
        return {}
    out = {}
    # each block runs from "(desktop):" or "(laptop):" to the next one
    for m in re.finditer(r'\((desktop|laptop)\):(.*?)(?=AAPL,ig-platform-id|Needed kexts|$)',
                         txt, re.S):
        where, body = m.group(1), m.group(2)
        found = []
        for value, label, swapped in re.findall(
                r'(0x[0-9A-Fa-f]{8})\s*(?:\(([^)]*)\))?\s*([0-9A-Fa-f]{8})?', body):
            if not swapped:
                continue
            found.append({'value': value.lower(), 'data': swapped.lower(),
                          'label': (label or '').strip()})
        if found:
            out[where] = found
    return out


def parse_intel(page):
    """Generation sections, tagged Native or Unsupported, with their models."""
    body = page[page.index('<main'):] if '<main' in page else page
    chunks = re.split(r'<h([23])[^>]*>(.*?)</h\1>', body, flags=re.S)
    out, group, i = [], None, 1
    while i < len(chunks):
        lvl = chunks[i]
        head = html.unescape(re.sub(r'<[^>]+>', '', chunks[i + 1])).strip().lstrip('# ')
        seg = chunks[i + 2]
        if lvl == '2':
            group = head
        elif group:
            models = []
            for li in re.findall(r'<li>(.*?)</li>', seg, re.S):
                txt = re.sub(r'\s+', ' ',
                             html.unescape(re.sub(r'<[^>]+>', '', li))).strip()
                if re.match(r'^(HD|UHD|Iris|Intel)\b', txt) and 'guide' not in txt:
                    models.append(txt)
            profiles = IGPU_GENERATIONS.get(head, [])
            if models and (profiles or 'Discrete' in head):
                entry = {'section': head,
                         'status': 'works' if group.startswith('Native') else 'unsupported',
                         'profiles': profiles, 'models': models}
                for where, cands in parse_framebuffers(seg).items():
                    entry[f'{where}_platform_id'] = cands
                out.append(entry)
        i += 3
    return out


# NVIDIA names no device ids anywhere on its page - only card models under a
# family heading. What ties a detected card to a family instead is the chip
# codename, which the PCI ID Project puts in the device name: 10de:1180 is
# "GK104 [GeForce GTX 680]", and GK is Kepler. Two letters, and both sides of
# the join are read rather than typed.
NVIDIA_CHIPS = {
    'GF': 'Fermi', 'GK': 'Kepler', 'GM': 'Maxwell', 'GP': 'Pascal',
    'GV': 'Volta', 'TU': 'Turing', 'GA': 'Ampere', 'AD': 'Ada', 'GB': 'Blackwell',
}

# Which heading on the page speaks for which chip family. The page groups by
# marketing series, and a series is not a chip: the 700 series holds Kepler and
# rebranded Fermi both, and the page says so in a section of its own.
NVIDIA_SECTIONS = {
    'Kepler Series': ('GK',),
    'Maxwell Series': ('GM',),
    'Pascal Series': ('GP',),
    'Volta Series': ('GV',),
    'Turing Series': ('TU',),
    'Ampere Series': ('GA',),
    'Hopper Series': ('GH',),
    'Lovelace Series': ('AD',),
    'Blackwell Series': ('GB',),
    'Fermi rebranded': ('GF',),
    # A warning about four Kepler cards, with no versions of its own. Listed so
    # it opens a section of its own and is dropped, rather than being read as
    # the Kepler heading and swallowing the next family's lines.
    'Kepler Series(GK106': (),
}

# The asterisk on Volta's line is a footnote, not part of the version.
MACOS_NAMED = re.compile(r'^(Highest|Initial) Supported OS:\s*(.+?)\s*\(([\d.]+)\)\s*\*?\s*$')
# "Highest Supported OS: None" - Turing says it in the same place the others
# say a version, and it is the clearest statement on the page.
MACOS_NONE = re.compile(r'^(Highest|Initial) Supported OS:\s*None\s*$')


def _plain_lines(page):
    body = re.sub(r'<script.*?</script>', '', page, flags=re.S)
    text = html.unescape(re.sub(r'<[^>]+>', '\n', body))
    return [l.strip() for l in text.splitlines() if l.strip()]


def parse_nvidia(page):
    """Per-family support, from the page's own "Supported OS" lines.

    Every family section states two of them - the oldest macOS that ever drove
    the family and the newest that still does - and then lists the cards. Both
    are read; nothing here decides what a family supports."""
    lines = _plain_lines(page)
    # Keyed by the heading, because the page prints every heading twice: once
    # in its contents and once over the section itself. Appending both put the
    # contents copies first and the "Supported OS" lines then landed on
    # whichever of them happened to be open - Turing's "None" ended up on
    # Kepler, and Kepler came out as a family that never worked.
    sections, current = {}, None
    for line in lines:
        # Longest first: "Kepler Series(GK106" has to win over "Kepler Series",
        # or the warning section is read as the family itself. The page writes
        # a space before the bracket sometimes and not others.
        heading = next((h for h in sorted(NVIDIA_SECTIONS, key=len, reverse=True)
                        if line == h or line.startswith(h + ' ')
                        or line.startswith(h + '(')), None)
        if heading:
            # Where the heading names its chips - "Fermi rebranded(GF108,
            # GF117 and GF119)" - those are the chips, not the whole prefix.
            # That section is about three rebadged parts, and reading it as
            # every GF chip made a GTX 460 into a rebranded card.
            named_chips = re.findall(r'\bG[FKMPVA]\d{3}\b', line)
            current = sections.setdefault(heading, {
                'family': tuple(named_chips) or NVIDIA_SECTIONS[heading],
                'name': line, 'source': NVIDIA_URL})
            continue
        if not current:
            continue
        named = MACOS_NAMED.match(line)
        if named:
            which = 'highest' if named.group(1) == 'Highest' else 'lowest'
            current[which] = {'name': named.group(2), 'version': named.group(3)}
            continue
        if MACOS_NONE.match(line):
            current['highest'] = None
            current['never'] = True
    # a section with no "Supported OS" line under it said nothing to record
    return [f for f in sections.values() if 'highest' in f and f['family']]


# Families stated in prose. Each carries the sentence it rests on so the claim
# can be checked without going back to the page.
FAMILIES = [
    # whole_vendor: the sentence is about every card the vendor makes, so the
    # PCI vendor id is enough to apply it. Without that, a card whose reported
    # name does not happen to contain "nvidia" - and plenty do not - fell
    # through to unknown. Intel cannot be treated that way: 8086 is also every
    # integrated GPU, which is why the Arc rule still matches on the name.
    {'vendor': '10de', 'match': 'nvidia', 'whole_vendor': True,
     'name': 'NVIDIA, every series',
     'status': 'unsupported',
     'quote': 'There are no currently supported NVIDIA GPUs.',
     'source': f'{BASE}/modern-gpus/nvidia-gpu.html',
     'note': 'Kepler was the last supported family and it ended with Big Sur; '
             'Maxwell and Pascal stop at High Sierra; Turing and newer never had a driver.'},
    {'vendor': '8086', 'match': 'arc', 'name': 'Intel Arc, discrete',
     'status': 'unsupported',
     'quote': 'So Intel finally made a discrete GPU. Lmao. All of them are unsupported.',
     'source': f'{BASE}/modern-gpus/intel-gpu.html',
     'note': 'The page names the Alchemist cards; Battlemage is not listed '
             'individually but falls under the same statement.'},
]


def _flatten(family):
    """One TOML table per family. Nested optional tables read worse than four
    plain keys, and two of them are absent for a family that never worked."""
    out = {'chips': list(family['family']), 'name': family['name'],
           'source': family['source'],
           'status': 'unsupported' if family.get('never') else 'works'}
    for end in ('lowest', 'highest'):
        value = family.get(end)
        if value:
            out[f'{end}_name'] = value['name']
            out[f'{end}_version'] = value['version']
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='data/gpu.toml')
    a = ap.parse_args()

    cards = parse_amd(fetch(AMD_URL))
    igpus = parse_intel(fetch(INTEL_URL))
    nvidia = parse_nvidia(fetch(NVIDIA_URL))
    if len(nvidia) < 4:
        sys.exit(f'only parsed {len(nvidia)} NVIDIA families; the page changed')
    if len(cards) < 40:
        sys.exit(f'only parsed {len(cards)} AMD cards; the page layout probably changed')
    ocgen.write_toml(Path(a.out), {'card': cards, 'igpu': igpus, 'family': FAMILIES,
                                   'nvidia': [_flatten(f) for f in nvidia]},
                     '# GPU support, from Dortania\'s GPU Buyers Guide.\n'
                     '#\n'
                     '# The AMD entries are parsed from the guide\'s own tables, which give a\n'
                     '# PCI device id per card - so a detected GPU is looked up rather than\n'
                     '# matched by name. NVIDIA and Intel state support by family in prose,\n'
                     '# so those are written as family rules carrying the sentence they rest\n'
                     '# on. Regenerate with tools/gputable.py.\n'
                     f'# Source: {AMD_URL}')
    from collections import Counter
    c = Counter(x['status'] for x in cards)
    print(f'  {len(cards)} AMD cards: {dict(c)}')
    print(f'  {len(igpus)} intel igpu sections: '
          + ', '.join(f'{g["section"][:18]}={g["status"][:5]}' for g in igpus))
    print(f'  {len(FAMILIES)} family rules')
    fams = sorted({x['family'] for x in cards})
    print('  families:', ', '.join(f for f in fams if f)[:150])


if __name__ == '__main__':
    main()
