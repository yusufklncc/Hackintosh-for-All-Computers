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
import deviceids
import ocgen
import oclptable
import provenance
import summary
import thirdparty

LOCK = Path('vendor/kexts.lock')
CATALOGUE = Path('profiles/catalogue.toml')
SHIPPED = Path('EFI/OC/Kexts')
OPENCORE = Path('vendor/opencore')
LICENCE = Path('LICENSE')
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


CATEGORIES = ('Ethernet', 'Wi-Fi', 'Bluetooth', 'Trackpad', 'Graphics',
              'Audio', 'Card reader', 'Mac')

ROLE_CATEGORY = {'ethernet': 'Ethernet', 'wifi': 'Wi-Fi',
                 'bluetooth': 'Bluetooth', 'trackpad': 'Trackpad'}


# The tables were written at different times and say the same thing two ways.
# A filter offering both "works" and "supported" asks the reader to know that.
ONE_WORD = {'works': 'supported', 'works-spoofed': 'spoofed'}


def _entry(category, ident, name, note, vendor=None, kext=None, macos=None,
           status='supported'):
    """One row. `status` is its own field, not the first word of a sentence.

    It was inside the note - "works, Polaris 10 and 20 series" - which reads
    fine and cannot be filtered on or coloured. A catalogue of seven hundred
    rows where the verdict is prose is a catalogue nobody can scan."""
    return {'category': category, 'id': ident, 'name': name, 'vendor': vendor,
            'kext': kext, 'note': note, 'macos': macos,
            'status': ONE_WORD.get(status, status)}


def devices():
    """Everything this repository has a name and a verdict for, as a flat list.

    One row per device, in one shape, so a front end can search and filter it
    without knowing which table each row came from. The tables themselves stay
    where they are: this reads them, it does not become a second copy of them.

    An id the upstream name lists do not carry keeps its id as its name. That
    is not a gap in what this repository drives - the kext still matches it -
    only in what anybody has written down about what to call it."""
    named, vendor_names = deviceids.names(), deviceids.vendors()

    def called(ident):
        return named.get(ident.lower()), vendor_names.get(ident.split(':')[0].lower())

    out = []

    # what the kexts themselves bind to, read out of the kexts
    for driver in ocgen.read_toml(HARDWARE).get('driver', []):
        category = ROLE_CATEGORY.get(driver['role'])
        if not category:
            continue
        for ident in driver['ids']:
            name, vendor = called(ident)
            # a kext here binds to this id: that is the whole claim
            out.append(_entry(category, ident, name or ident, driver['label'],
                              vendor=vendor, kext=driver['kext']))

    graphics = ocgen.read_toml(Path('data/gpu.toml'))
    for card in graphics.get('card', []):
        # the guide's own model name, not the upstream one: nine cards share
        # the id 1002:67df and the upstream list calls all nine "Ellesmere
        # [Radeon RX 470/480/570/580/590]". The model is the thing somebody is
        # looking for.
        _, vendor = called(card['id'])
        note = card['status']
        if card.get('family'):
            note = f"{card['status']}, {card['family']}"
        patched = oclptable.for_card_family(card.get('family') or '')
        top = oclptable.upper_bound()
        out.append(_entry('Graphics', card['id'], card.get('name') or card['id'],
                          card.get('family') or '', vendor=vendor,
                          status=card['status'],
                          macos=({'from': None, 'to': None, 'oclp': patched['from'],
                                  'oclp_to': top[1] if top else None}
                                 if patched else None)))
    for family in graphics.get('family', []):
        out.append(_entry('Graphics', family.get('vendor'), family.get('label')
                          or family.get('match'), family.get('note') or '',
                          status=family['status']))
    for family in graphics.get('nvidia', []):
        span = ('never supported' if family['status'] != 'works'
                else f"macOS {family['lowest_name']} {family['lowest_version']} to "
                     f"{family['highest_name']} {family['highest_version']}")
        short = family['name'].split(' Series')[0].split('(')[0].strip()
        # a row per card, the way the AMD table reads. The page names no device
        # ids for NVIDIA, so the chip family stands in the id column - it is
        # what the verdict is actually keyed on.
        patched = (oclptable.for_nvidia(family['chips'][0])
                   if family['chips'] else None)
        if patched:
            span += f", OCLP from macOS {patched['from']}"
        top = oclptable.upper_bound()
        macos = (None if family['status'] != 'works' else
                 {'from': family['lowest_version'], 'to': family['highest_version'],
                  'oclp': patched['from'] if patched else None,
                  'oclp_to': top[1] if (patched and top) else None})
        for card in family['cards']:
            out.append(_entry('Graphics', ', '.join(family['chips']), card, short,
                              vendor='NVIDIA Corporation', macos=macos,
                              status=family['status']))
        if not family['cards']:
            out.append(_entry('Graphics', ', '.join(family['chips']),
                              family['name'], short, vendor='NVIDIA Corporation',
                              macos=macos, status=family['status']))
    for igpu in graphics.get('igpu', []):
        patched = next((oclptable.for_igpu(pr) for pr in igpu.get('profiles', [])
                        if oclptable.for_igpu(pr)), None)
        top = oclptable.upper_bound()
        out.append(_entry('Graphics', None, igpu.get('label') or 'Intel iGPU',
                          ', '.join(igpu.get('profiles', [])), vendor='Intel Corporation',
                          status=igpu['status'],
                          macos=({'from': None, 'to': None, 'oclp': patched['from'],
                                  'oclp_to': top[1] if top else None}
                                 if patched else None)))

    for codec in ocgen.read_toml(Path('data/audio.toml')).get('audio', []):
        layouts = codec.get('layout') or []
        # hda_id, not id: the codec table keys on the HD audio pair and the
        # column was empty for all hundred and ten of them
        out.append(_entry('Audio', codec.get('hda_id'),
                          f"{codec.get('vendor', '')} {codec.get('codec', '')}".strip(),
                          f'{len(layouts)} layout'
                          + ('s' if len(layouts) != 1 else '') + ' to try',
                          kext='AppleALC.kext', vendor=codec.get('vendor')))

    readers = ocgen.read_toml(Path('data/cardreader.toml'))
    driver = readers.get('driver', {})
    for reader in readers.get('device', []):
        name, vendor = called(reader['id'])
        out.append(_entry('Card reader', reader['id'], name or reader['id'],
                          ('since ' + str(reader.get('since'))
                           if reader.get('supported') else 'listed, not driven yet'),
                          vendor=vendor, kext=driver.get('kext'),
                          status='supported' if reader.get('supported')
                                 else 'unsupported'))

    macs = ocgen.read_toml(Path('data/mac.toml'))
    for mac in macs.get('mac', []):
        out.append(_entry('Mac', mac['board'], mac['board'],
                          'Apple silicon' if mac['board'].startswith('J') else 'Intel',
                          vendor='Apple',
                          macos={'from': mac['floor'], 'to': mac['ceiling'] or None},
                          # Apple still lists it, or it fell off the list
                          status='supported' if not mac['ceiling'] else 'dropped'))
    # One row per device, not one per kext that claims it. Broadcom Bluetooth
    # is three kexts in a relay and every adapter was appearing three times;
    # the same card listed twice in the card table appeared twice as well.
    merged = {}
    for entry in out:
        # keyed on the name for graphics, where one id covers many models, and
        # on the id everywhere else, where one device has many claimants
        key = ((entry['category'], entry['name']) if entry['category'] == 'Graphics'
               else (entry['category'], entry['id'] or entry['name']))
        if key in merged:
            kept = merged[key]
            for kext in (entry['kext'] or '').split(', '):
                if kext and kext not in (kept['kext'] or ''):
                    kept['kext'] = f"{kept['kext']}, {kext}" if kept['kext'] else kext
            continue
        merged[key] = entry
    out = list(merged.values())
    return {'t': 'devices', 'devices': out,
            'categories': [c for c in CATEGORIES
                           if any(d['category'] == c for d in out)],
            'vendors': sorted({d['vendor'] for d in out if d['vendor']}),
            'statuses': sorted({d['status'] for d in out})}


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
        # the licence on this repository itself, read from the file rather
        # than written into a sentence that can go stale
        'licence': (LICENCE.read_text(encoding='utf-8').splitlines()[0].strip()
                    if LICENCE.exists() else None),
        'repo': 'https://github.com/yusufklncc/Hackintosh-for-All-Computers',
    }


def main(argv=None):
    import argparse
    import json
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('what', choices=('kexts', 'about', 'devices'))
    a = ap.parse_args(argv)
    document = {'kexts': kexts, 'about': about, 'devices': devices}[a.what]()
    print(json.dumps(document,
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
