"""Everything this repository ships that somebody else wrote, and what it is under.

Two questions, one report.

**What we ship.** Thirty-seven kexts come from nineteen upstream projects, under
six different licences and, in five cases, under none stated at all. A file
named LICENSE at the top of this repository covers what is written here; it says
nothing about a binary somebody else compiled. `--refresh` reads each project's
own licence from GitHub into vendor/licences.toml, so the answer is recorded
rather than assumed.

**What we do not ship.** data/candidates.toml lists driver projects for hardware
this repository has no answer for, each one checked to exist and each with the
licence that would decide whether it could be vendored. `--fetch` downloads each
one's latest release and counts the devices it would add, using the same reader
that builds data/hardware.toml, so the number is the kext's own and not an
estimate.

    python3 tools/thirdparty.py                 # the report, offline
    python3 tools/thirdparty.py --machine r.json
    python3 tools/thirdparty.py --refresh       # re-read the licences (network)
    python3 tools/thirdparty.py --fetch         # count what a candidate adds (network)
"""
import argparse
import io
import json
import os
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import advise
import detect
import hwtable
import ocgen
import ui

LOCK = Path('vendor/kexts.lock')
LICENCES = Path('vendor/licences.toml')
CANDIDATES = Path('data/candidates.toml')

BOLD, DIM, GREEN, YELLOW, RED, RESET = ui.colours('bold', 'dim', 'green', 'yellow', 'red', 'reset')

# A licence that grants nothing is not the same as a permissive one, and a
# copyleft licence is not a problem - it is an obligation. Both are worth
# seeing at a glance; neither is a verdict on whether to ship the kext.
NONE_STATED = 'none stated'
ATTENTION = (NONE_STATED,)


def upstreams():
    """{repo: [kext, ...]} from the lock, which already records where each came from."""
    out = {}
    for kext, info in ocgen.read_toml(LOCK)['kext'].items():
        repo = info.get('upstream')
        if repo:
            out.setdefault(repo, []).append(kext)
    return out


def read_licences():
    if not LICENCES.exists():
        return {}
    return {e['repo']: e for e in ocgen.read_toml(LICENCES).get('upstream', [])}


def fetch_licence(repo):
    """(spdx, name) as GitHub reads the project's own LICENSE file."""
    try:
        with urllib.request.urlopen(
                f'https://api.github.com/repos/{repo}/license', timeout=30) as r:
            d = json.load(r)['license']
        spdx = d.get('spdx_id')
        return (NONE_STATED if spdx in (None, 'NOASSERTION') and not d.get('name')
                else spdx if spdx and spdx != 'NOASSERTION' else d.get('name', 'Other'),
                d.get('name', ''))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return NONE_STATED, 'no LICENSE file in the repository'
        raise


def refresh():
    rows = []
    for repo, kexts in sorted(upstreams().items()):
        spdx, name = fetch_licence(repo)
        rows.append({'repo': repo, 'licence': spdx, 'described': name,
                     'kexts': sorted(kexts)})
        print(f'  {repo:38s} {spdx}')
    ocgen.write_toml(LICENCES, {'upstream': rows},
                     '# The licence each vendored kext is under, read from the\n'
                     "# project's own LICENSE file by tools/thirdparty.py --refresh.\n"
                     '#\n'
                     '# The LICENSE at the root of this repository covers what is\n'
                     '# written here. It says nothing about a binary somebody else\n'
                     '# compiled, which is why this file exists.\n'
                     '#\n'
                     '# "none stated" means the project has no LICENSE file at all.\n'
                     '# That is not permission; it is the absence of one.')
    return 0


def candidates():
    if not CANDIDATES.exists():
        return []
    return ocgen.read_toml(CANDIDATES).get('candidate', [])


def fetch_ids(repo):
    """Device ids in a project's latest release, read from the kext itself."""
    with urllib.request.urlopen(
            f'https://api.github.com/repos/{repo}/releases/latest', timeout=30) as r:
        release = json.load(r)
    assets = [a for a in release['assets'] if a['name'].lower().endswith('.zip')]
    prefer = [a for a in assets if 'debug' not in a['name'].lower()] or assets
    if not prefer:
        return release.get('tag_name', ''), set()
    with urllib.request.urlopen(prefer[0]['browser_download_url'], timeout=120) as r:
        blob = r.read()
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            z.extractall(tmp)
        ids = set()
        for info in Path(tmp).rglob('Info.plist'):
            kext = info.parent.parent
            if not kext.name.endswith('.kext'):
                continue
            import plistlib
            with open(info, 'rb') as fh:
                plist = plistlib.load(fh)
            for p in (plist.get('IOKitPersonalities') or {}).values():
                ids |= hwtable.pci_ids(p.get('IOPCIPrimaryMatch', ''))
                ids |= hwtable.pci_ids(p.get('IOPCIMatch', ''))
                ids |= hwtable.name_ids(p.get('IONameMatch'))
                v, d = p.get('idVendor'), p.get('idProduct')
                if isinstance(v, int) and isinstance(d, int):
                    ids.add(f'{v:04x}:{d:04x}')
    return release.get('tag_name', ''), ids


def fetch_candidates():
    rows = candidates()
    for c in rows:
        try:
            tag, ids = fetch_ids(c['repo'])
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            # an archived project often has source and no release. Recording
            # that is more use than an empty row that looks like a fetch nobody
            # ran: it says the kext would have to be built to be vendored.
            c['release'] = ''
            c['ids'] = []
            c['unreleased'] = True
            print(f'  {c["name"]:24s} no release published')
            continue
        c['release'] = tag
        c['ids'] = sorted(ids)
        c.pop('unreleased', None)
        print(f'  {c["name"]:24s} {tag:12s} {len(ids)} device ids')
    ocgen.write_toml(CANDIDATES, {'candidate': rows},
                     Path(CANDIDATES).read_text().split('[[candidate]]')[0].rstrip('\n'))
    return 0


def vendored_tools():
    """Programs vendored whole, which are not kexts and are licensed separately."""
    lock = Path('vendor/tools.lock')
    if not lock.exists():
        return []
    return [dict(path=k, **v) for k, v in ocgen.read_toml(lock)['tool'].items()]


def report(hw=None):
    lic = read_licences()
    ours = upstreams()
    print(f'{BOLD}What this repository ships{RESET}  '
          f'{DIM}{sum(len(v) for v in ours.values())} kexts from '
          f'{len(ours)} projects{RESET}\n')
    by_licence = {}
    for repo in sorted(ours):
        entry = lic.get(repo, {})
        by_licence.setdefault(entry.get('licence', 'not read'), []).append(repo)
    for licence in sorted(by_licence):
        colour = RED if licence in ATTENTION else GREEN
        print(f'  {colour}{licence:22s}{RESET} {len(by_licence[licence])}')
        for repo in by_licence[licence]:
            kexts = ', '.join(k.replace('.kext', '') for k in sorted(ours[repo]))
            print(f'      {repo:38s} {DIM}{kexts}{RESET}')
    orphan = sorted(k for k in ocgen.read_toml(LOCK)['kext']
                    if not ocgen.read_toml(LOCK)['kext'][k].get('upstream'))
    if orphan:
        print(f'  {YELLOW}{"no upstream recorded":22s}{RESET} {len(orphan)}')
        print(f'      {DIM}{", ".join(k.replace(".kext", "") for k in orphan)}{RESET}')
    missing = by_licence.get(NONE_STATED, [])
    if missing:
        print(f'\n  {RED}{len(missing)} of these state no licence at all.{RESET} '
              f'{DIM}That is not permission; it is the\n  absence of one. Shipping '
              f'them is a decision this report only makes visible.{RESET}')

    tools = vendored_tools()
    if tools:
        print(f'\n{BOLD}Programs vendored whole{RESET}  '
              f'{DIM}not kexts, and licensed separately{RESET}\n')
        for tool in tools:
            print(f'  {tool["path"]:28s} {GREEN}{tool["license"]:16s}{RESET} '
                  f'v{tool["version"]}  {DIM}{tool["upstream"]}{RESET}')
            if tool.get('note'):
                print(f'      {DIM}{tool["note"]}{RESET}')

    rows = candidates()
    if not rows:
        return 0
    print(f'\n{BOLD}What it does not ship{RESET}  '
          f'{DIM}drivers for hardware with no answer here{RESET}\n')
    have = {i for d in ocgen.read_toml('data/hardware.toml')['driver'] for i in d['ids']}
    seen = set()
    if hw:
        seen = {i.lower() for i in (hw.get('pci_ids') or []) + (hw.get('usb_ids') or [])}
    for c in rows:
        ids = set(c.get('ids') or [])
        new = ids - have
        colour = RED if c['licence'] in ATTENTION else GREEN
        line = f'  {c["name"]:24s} {colour}{c["licence"]:16s}{RESET} '
        line += (f'{len(new)} new ids' if ids else
                 f'{YELLOW}no release to read{RESET}' if c.get('unreleased') else
                 f'{DIM}not counted yet{RESET}')
        if c.get('archived'):
            line += f'  {YELLOW}archived{RESET}'
        print(line)
        print(f'      {DIM}{c["covers"]}{RESET}')
        here = sorted(new & seen)
        if here:
            print(f'      {GREEN}on this machine: {", ".join(here)}{RESET}')
    if hw:
        unclaimed = seen - have - {i for c in rows for i in c.get('ids') or []}
        print(f'\n  {DIM}{len(unclaimed)} of this machine\'s devices are claimed by '
              f'nothing here and by none of these.{RESET}')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--refresh', action='store_true',
                    help="re-read each project's licence from GitHub")
    ap.add_argument('--fetch', action='store_true',
                    help='download each candidate and count its device ids')
    ap.add_argument('--machine', metavar='FILE', help='a hardware report to check against')
    a = ap.parse_args(argv)
    if a.refresh:
        return refresh()
    if a.fetch:
        return fetch_candidates()
    hw = None
    if a.machine:
        hw, complaint = detect.read_report(a.machine)
        if complaint:
            sys.exit(complaint)
    return report(hw)


if __name__ == '__main__':
    sys.exit(main())
