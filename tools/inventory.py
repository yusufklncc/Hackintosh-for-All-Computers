"""What this repository carries, as values.

Two documents a front end can draw: the kexts that are vendored here, and the
standing facts about the program itself. Both are read from the same files the
build reads, so a number on a screen cannot drift from the tree it describes -
the window used to carry "OpenCore 1.0.6" and "41 kexts" written by hand, and
both were wrong.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen
import provenance
import summary
import thirdparty

LOCK = Path('vendor/kexts.lock')
CATALOGUE = Path('profiles/catalogue.toml')
SHIPPED = Path('EFI/OC/Kexts')
OPENCORE = Path('vendor/opencore')
HARDWARE = Path('data/hardware.toml')


def opencore_version():
    """The version vendored here, which is the directory it lives in."""
    if not OPENCORE.is_dir():
        return None
    versions = sorted(p.name for p in OPENCORE.iterdir() if p.is_dir())
    return versions[-1] if versions else None


def _roles():
    """kext -> what it drives, from the table generated out of the kexts."""
    out = {}
    if not HARDWARE.exists():
        return out
    for d in ocgen.read_toml(HARDWARE).get('driver', []):
        entry = out.setdefault(d['kext'], {'roles': [], 'labels': [], 'devices': 0})
        if d['role'] not in entry['roles']:
            entry['roles'].append(d['role'])
        if d['label'] not in entry['labels']:
            entry['labels'].append(d['label'])
        entry['devices'] += len(d.get('ids', []))
    return out


def kexts():
    """Every vendored kext, with where it came from and what it drives.

    A kext with no row in the hardware table is not an omission: the table is
    generated from the kexts that bind to a device id, and several of these -
    Lilu, VirtualSMC - bind to nothing and are there for the ones that do."""
    if not LOCK.exists():
        return {'t': 'kexts', 'kexts': []}
    roles = _roles()
    out = []
    for bundle in sorted(ocgen.read_toml(LOCK)['kext']):
        facts = summary.kext_facts(bundle)
        drives = roles.get(bundle)
        out.append({
            **facts,
            'roles': drives['roles'] if drives else [],
            'label': ', '.join(drives['labels']) if drives else None,
            'devices': drives['devices'] if drives else 0,
        })
    return {'t': 'kexts', 'kexts': out}


def about():
    """The standing facts, each read from the file that decides it."""
    configs = (len(ocgen.read_toml(CATALOGUE)['config'])
               if CATALOGUE.exists() else 0)
    vendored = len(ocgen.read_toml(LOCK)['kext']) if LOCK.exists() else 0
    sources = [
        {'area': row['area'], 'kind': row['kind'], 'file': row['file'],
         'source': row['source'], 'count': row['count'],
         'covers': row['covers'], 'gap': row['gap']}
        for row in provenance.catalogue()
    ]
    tally = {}
    for row in sources:
        tally[row['kind']] = tally.get(row['kind'], 0) + 1
    return {
        't': 'about',
        'opencore': opencore_version(),
        'configs': configs,
        'kexts': vendored,
        'shipped': len(list(SHIPPED.iterdir())) if SHIPPED.is_dir() else 0,
        # the whole point of the thing: it never reaches the network, because
        # the machine being converted usually cannot
        'offline': True,
        'sources': sources,
        'tally': tally,
        'tools': thirdparty.vendored_tools(),
    }


def main(argv=None):
    import argparse
    import json
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('what', choices=('kexts', 'about'))
    a = ap.parse_args(argv)
    print(json.dumps(kexts() if a.what == 'kexts' else about(),
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
