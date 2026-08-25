"""What the detected graphics hardware means for a build.

The rule this follows, in order:

  a card macOS supports          say so, and give the boot arguments its family
                                 needs
  a card macOS does not support  say so plainly. Offer falling back to the
                                 integrated GPU only if there is one and it is
                                 itself supported - suggesting a fallback that
                                 does not exist wastes somebody's evening. Name
                                 a card that would work either way.
  a card nobody has reported     say that, rather than implying either answer

Everything comes from data/gpu.toml, which carries Dortania's verdict per PCI
id for AMD and per family for the rest.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deviceids
import ocgen
import oclptable

TABLE = Path('data/gpu.toml')

# Integrated graphics live on the CPU vendor's id at the usual iGPU slot; a
# discrete card is anything else. This only has to be right often enough to
# phrase the advice, and the ids are shown so a wrong guess is visible.
IGPU_HINTS = ('hd graphics', 'uhd graphics', 'iris', 'intel graphics', 'vega')

VERDICT = {
    'works': 'supported',
    'works-spoofed': 'supported with a device-id spoof',
    'untested': 'should work, but nobody has reported it',
    'unsupported': 'not supported',
    'unknown': 'unknown',
}


def load():
    if not TABLE.exists():
        sys.exit(f'{TABLE} missing; run tools/gputable.py')
    d = ocgen.read_toml(TABLE)
    return ({c['id']: c for c in d['card']}, d.get('family', []), d.get('igpu', []),
            d.get('nvidia', []))


FIELD = Path('data/field.toml')
FRAMEBUFFERS = Path('data/framebuffer.toml')


def native_ids(generation):
    """The device ids WhateverGreen says need no faked device-id.

    A generation being supported is not the same as every part in it being
    supported: Whiskey Lake and Coffee Lake Refresh are in supported generations
    and missing from these lists, and the document says what they need instead.
    Absent from the list therefore means "not native", never "unsupported"."""
    if not generation or not FRAMEBUFFERS.exists():
        return set()
    return {e['id'] for e in ocgen.read_toml(FRAMEBUFFERS).get('native', [])
            if generation in e.get('profiles', [])}


def field_igpu(cpu_name):
    """A field report about this exact processor's iGPU, if there is one.

    Support is documented per generation and per device id, and neither reaches
    a single SKU. A processor whose iGPU behaves differently from the rest of
    its generation can only be recorded from someone having run it, so the entry
    carries who ran it and what they saw."""
    if not cpu_name or not FIELD.exists():
        return None
    haystack = cpu_name.lower()
    for e in ocgen.read_toml(FIELD).get('igpu', []):
        if e['cpu'].lower() in haystack:
            return e
    return None


def igpu_verdict(generation):
    """Intel iGPU support for a CPU generation, or None if not covered.

    Keyed on the CPU rather than the adapter name: the guide writes "UHD
    Graphics for 12th Gen Intel Processors" where Windows reports "UHD Graphics
    770", and guessing across that gap is how a wrong answer gets stated
    confidently. A generation listed both ways has model exceptions, so the
    supported reading wins and the exception is named."""
    if not generation:
        return None, None
    _, _, igpus, _ = load()
    hits = [g for g in igpus if generation in g.get('profiles', [])]
    if not hits:
        return None, None
    works = [g for g in hits if g['status'] == 'works']
    if works:
        excs = [m for g in hits if g['status'] == 'unsupported' for m in g['models']]
        return 'works', excs
    return 'unsupported', hits[0]['models']


def looks_integrated(name):
    n = (name or '').lower()
    return any(h in n for h in IGPU_HINTS) and 'arc' not in n


NVIDIA_CHIP = re.compile(r'\b(G[FKMPVA]|TU|AD|GB|GH)\d{3}\b')


def nvidia_family(device):
    """The NVIDIA family a card belongs to, from its chip codename, or None.

    The guide states support by family and names no device ids. The PCI ID
    Project puts the chip in the device name - 10de:1180 is "GK104 [GeForce GTX
    680]" - and the first two letters are the family. Both halves are read: the
    guide for what a family supports, the id list for which family a card is.

    A card the id list has no name for gets no family, and falls through to the
    whole-vendor rule rather than to a guess."""
    if not (device.get('id') or '').lower().startswith('10de:'):
        return None
    _, name = deviceids.describe(device['id'])
    found = NVIDIA_CHIP.search(name or '')
    if not found:
        return None
    chip, prefix = found.group(0), found.group(1)
    for family in load()[3]:
        chips = family.get('chips', [])
        # an exact chip beats a prefix: the rebranded-Fermi section names three
        # parts, and every other section speaks for a whole two-letter family
        if chip in chips or prefix in chips:
            return family
    return None


def classify(device, generation=None):
    """(verdict, detail) for one detected graphics device."""
    cards, families, _, _ = load()
    # before the whole-vendor rule, which says only "no NVIDIA GPU is currently
    # supported" - true of what is on sale and useless about a GTX 680
    nvidia = nvidia_family(device)
    if nvidia:
        entry = {'family': nvidia['name'], 'source': nvidia['source']}
        if nvidia['status'] == 'works':
            entry['note'] = (f"macOS {nvidia['lowest_name']} "
                             f"{nvidia['lowest_version']} to "
                             f"{nvidia['highest_name']} {nvidia['highest_version']}")
            entry['macos'] = (nvidia['lowest_version'], nvidia['highest_version'])
        else:
            entry['note'] = 'no driver was ever written for this family'
        # what happens past the native ceiling, where somebody else put the
        # drivers back. Information about an installed macOS, not something a
        # build does: OCLP patches the system after the fact.
        patched = oclptable.for_nvidia(nvidia['chips'][0]) if nvidia['chips'] else None
        if patched:
            entry['oclp'] = {'from': patched['from'], 'name': patched['name'],
                             'source': oclptable.table().get('source')}
        return nvidia['status'], entry
    card = cards.get(device.get('id') or '')
    if card:
        return card['status'], card
    name = (device.get('name') or '').lower()
    vendor = (device.get('id') or '').split(':')[0]
    for f in families:
        if f.get('whole_vendor') and f['vendor'] == vendor:
            return f['status'], f
        if f['match'] in name and f['vendor'] == vendor:
            return f['status'], f
    if looks_integrated(name) and vendor == '8086':
        state, models = igpu_verdict(generation)
        if state:
            entry = {'family': f'Intel iGPU, {generation}'}
            notes = []
            if state == 'works' and models:
                notes.append('except ' + ', '.join(models)
                             + ', which the guide lists as unsupported')
            if state == 'works':
                native = native_ids(generation)
                if native and device.get('id'):
                    if device['id'].lower() in native:
                        entry['family'] += ', natively supported'
                    else:
                        entry['family'] += ', not natively'
                        notes.append(
                            f'{device["id"]} is not among the ids this generation '
                            f'supports without a faked device-id')
            if notes:
                entry['note'] = '; '.join(notes)
                # the family string already carries the short form of this, and
                # the section below prints the note in full, so a table row does
                # not need both
                entry['long_note'] = True
            return state, entry
    return 'unknown', None


def report(devices, generation=None, cpu_name=None):
    """Lines describing the graphics situation, and the boot args to add.

    cpu_name is the processor as the machine reports it, which is the only thing
    a field report can be matched on."""
    lines, args = [], []
    if not devices:
        return ['  no graphics hardware was readable here'], args

    field = field_igpu(cpu_name)
    judged = []
    for d in devices:
        verdict, entry = classify(d, generation)
        if field and looks_integrated(d.get('name')):
            verdict = field['status']
            entry = {'family': f'{field["observed"]}, reported by '
                               f'{field["observed_by"]}',
                     'note': field.get('note', '')}
        judged.append((d, verdict, entry))
    igpu_state = field['status'] if field else igpu_verdict(generation)[0]
    igpu_state = 'works' if igpu_state == 'works' else igpu_state
    supported_igpu = [d for d, v, _ in judged
                      if looks_integrated(d.get('name'))
                      and (v in ('works', 'works-spoofed') or igpu_state == 'works')]

    for device, verdict, entry in judged:
        ident = f'  {device["name"]}' + (f'  [{device["id"]}]' if device.get('id') else '')
        lines.append(f'{ident}')
        lines.append(f'      {VERDICT.get(verdict, verdict)}'
                     + (f'   ({entry["family"]})' if entry and entry.get('family') else ''))
        if entry and entry.get('note'):
            lines.append(f'      {entry["note"]}')
        if entry and entry.get('quote'):
            lines.append(f'      "{entry["quote"]}"')
        for arg in (entry or {}).get('boot_args', []):
            if arg not in args:
                args.append(arg)
            lines.append(f'      needs boot argument {arg}')

        if verdict == 'unsupported' and not looks_integrated(device.get('name')):
            others = [d for d in supported_igpu if d is not device]
            integrated = [d for d, _, _ in judged
                          if looks_integrated(d.get('name')) and d is not device]
            if others:
                names = ', '.join(d['name'] for d in others)
                lines.append(f'      you can disable it and use {names} instead, '
                             f'which is supported')
            elif integrated and igpu_state == 'unsupported':
                lines.append('      the integrated GPU is not supported either, so there '
                             'is nothing to fall back to')
            elif integrated:
                # never claim there is no fallback when the answer is unknown
                lines.append('      whether the integrated GPU can be used instead could '
                             'not be determined')
            else:
                lines.append('      there is no integrated GPU here to fall back to')
            lines.append('      a supported card would be AMD Polaris, Vega or Navi 10/21/23')
    return lines, args


if __name__ == '__main__':
    cases = {
        'Arc B580 + supported iGPU': [
            {'name': 'Intel(R) Arc(TM) B580 Graphics', 'id': '8086:e20b'},
            {'name': 'Intel(R) HD Graphics 630', 'id': '8086:5912'}],
        'Arc B580 + Alder Lake iGPU': [
            {'name': 'Intel(R) Arc(TM) B580 Graphics', 'id': '8086:e20b'},
            {'name': 'Intel(R) UHD Graphics 770', 'id': '8086:4680'}],
        'Arc B580 alone': [{'name': 'Intel(R) Arc(TM) B580 Graphics', 'id': '8086:e20b'}],
        'RX 6600': [{'name': 'AMD Radeon RX 6600', 'id': '1002:73ff'}],
        'RX 580 2048SP': [{'name': 'AMD Radeon RX 580 2048SP', 'id': '1002:6fdf'}],
        'GTX 1050': [{'name': 'NVIDIA GeForce GTX 1050', 'id': '10de:1c8d'}],
        'RX 5700 XT': [{'name': 'AMD Radeon RX 5700 XT', 'id': '1002:731f'}],
    }
    gens = {'Arc B580 + supported iGPU': 'kaby-lake',
            'Arc B580 + Alder Lake iGPU': 'alder-lake',
            'Arc B580 alone': None}
    for label, devs in cases.items():
        print(f'\n=== {label} ===')
        lines, args = report(devs, gens.get(label))
        print('\n'.join(lines))
        if args:
            print(f'  -> boot-args: {" ".join(args)}')
