"""Which layout-id to try for the detected audio codec.

There is no single right answer here and pretending otherwise would waste
somebody's time. AppleALC ships a set of layouts per codec, each contributed for
a particular machine, and finding the one that works means trying them. So the
builder puts one in the config to boot with and writes the rest down, in the
order most likely to pay off:

  1. layouts whose contributor named the same brand as this machine
  2. layouts whose contributor named a machine at all
  3. the rest, lowest id first

That ordering is a heuristic about where to start, not a claim about which is
correct - which is why the alternatives are written out rather than hidden.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

TABLE = Path('data/audio.toml')


def load():
    if not TABLE.exists():
        sys.exit(f'{TABLE} missing; run tools/audiotable.py')
    return ocgen.read_toml(TABLE)['audio']


def find(hda_ids):
    """Codec entries for the detected HDA ids."""
    table = {c['hda_id']: c for c in load() if c['hda_id']}
    return [table[i] for i in hda_ids if i in table]


def rank(codec, brand=None):
    """Layouts, best first. brand is the OEM detection found, if any."""
    b = (brand or '').lower()

    def key(layout):
        note = (layout.get('note') or '').lower()
        if b and b in note:
            return (0, layout['id'])
        if note:
            return (1, layout['id'])
        return (2, layout['id'])
    return sorted(codec['layout'], key=key)


def report(hda_ids, brand=None):
    """(lines, alcid to use, next-steps text)."""
    found = find(hda_ids)
    if not found:
        if hda_ids:
            return ([f'  no audio codec here is in AppleALC\'s list '
                     f'({", ".join(hda_ids)})'], None, '')
        return (['  no audio codec was readable here'], None, '')

    lines, chosen, steps = [], None, []
    for codec in found:
        ordered = rank(codec, brand)
        lines.append(f'  {codec["vendor"]} {codec["codec"]}  [{codec["hda_id"]}]'
                     f'   {len(ordered)} layouts to try')
        if chosen is None and ordered:
            chosen = ordered[0]['id']
        for layout in ordered[:3]:
            mark = ' <- starting with this one' if layout['id'] == chosen else ''
            lines.append(f'      alcid={layout["id"]:<4d} {layout.get("note", "")[:58]}{mark}')
        if len(ordered) > 3:
            lines.append(f'      and {len(ordered) - 3} more, written to NEXT-STEPS.txt')

        steps.append(f'{codec["vendor"]} {codec["codec"]}  [{codec["hda_id"]}]')
        steps.append('')
        steps.append('  Audio needs a layout-id, and which one works depends on the')
        steps.append('  machine rather than the codec. The config was built with the')
        steps.append(f'  first of these. If sound does not work, or some ports do not,')
        steps.append('  change alcid= in boot-args to the next one and reboot.')
        steps.append('')
        for layout in ordered:
            note = layout.get('note', '')
            steps.append(f'    alcid={layout["id"]:<5d} {note}')
        steps.append('')
    return lines, chosen, '\n'.join(steps)


if __name__ == '__main__':
    for ids, brand in ((['10ec:0255'], 'lenovo'), (['10ec:0255'], None),
                       (['10ec:0269'], 'asus'), (['8086:2809'], None)):
        lines, alcid, _ = report(ids, brand)
        print(f'\n=== {ids} brand={brand} -> alcid={alcid} ===')
        print('\n'.join(lines))
