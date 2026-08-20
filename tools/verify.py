"""Equivalence gate.

Regenerates every published config from the profile set and compares it against
the hash recorded in profiles/catalogue.toml. Generated identity (serial, MLB,
UUID, ROM) is excluded because a profile never stores it; Comment strings are
excluded by default because they carry no runtime meaning.

If a checkout still has the old EFI/OC/config tree, the files there are used as
the reference instead. That is how the profiles were proven faithful before the
tree was removed.

The comparison is done on canonical XML bytes, not on decoded Python values:
True == 1 == 1.0 in Python, while <true/>, <integer>1</integer> and <real>1</real>
are three different things to OpenCore.

    python3 tools/verify.py <Sample.plist> [--profiles profiles] [--comments]
"""
import argparse
import glob
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen


def _row(e):
    return {'path': f"{ocgen.CONFIG_ROOT}/{e['name']}.plist",
            'platform': e['platform'], 'vendor': e.get('vendor'), 'cpu': e['cpu'],
            'chipset': e.get('chipset'), 'oem': e.get('oem'),
            'variant': e.get('variant'), 'cores': e.get('cores')}


def rehash(sample, profiles):
    """Recompute the catalogue hashes. Deliberate: the diff is what gets reviewed."""
    import hashlib
    path = profiles / 'catalogue.toml'
    text = path.read_text(encoding='utf-8')
    header = ''.join(l for l in text.splitlines(keepends=True) if l.startswith('#'))
    entries = ocgen.read_toml(path)['config']
    changed = 0
    for e in entries:
        row = _row(e)
        built = ocgen.assemble(sample, ocgen.layer_chain(row, profiles),
                               ocgen.build_params(row))
        new = hashlib.sha256(ocgen.canonical_bytes(built, True)).hexdigest()
        changed += new != e['sha256']
        e['sha256'] = new
    ocgen.write_toml(path, {'config': entries}, header.rstrip('\n'))
    print(f'  {changed}/{len(entries)} catalogue hashes changed')
    return 0


def against_catalogue(sample, profiles, comments):
    """Once EFI/OC/config is gone, the catalogue's hashes are the reference."""
    import hashlib
    entries = ocgen.read_toml(profiles / 'catalogue.toml')['config']
    ok, bad = 0, []
    for e in entries:
        # a catalogue entry *is* a published config, so it must pick up its
        # per-config residual; the name is what resolves that file
        row = _row(e)
        built = ocgen.assemble(sample, ocgen.layer_chain(row, profiles),
                               ocgen.build_params(row))
        got = hashlib.sha256(ocgen.canonical_bytes(built, True)).hexdigest()
        if got == e['sha256']:
            ok += 1
        else:
            bad.append((e['name'], e['sha256'][:12], got[:12]))
    for name, want, got in bad:
        print(f'CHANGED {name}\n    catalogue {want}  built {got}')
    print(f'\n  {ok}/{len(entries)} catalogue configs match their recorded hash')
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sample', nargs='?',
                    help='Sample.plist to build on; defaults to the vendored one')
    ap.add_argument('--profiles', default='profiles')
    ap.add_argument('--comments', action='store_true', help='also require Comment strings to match')
    ap.add_argument('-v', '--verbose', action='store_true')
    ap.add_argument('--rehash', action='store_true',
                    help='rewrite catalogue hashes from current output; the diff is the review')
    a = ap.parse_args()
    a.sample = a.sample or ocgen.vendored_sample()
    if not a.sample:
        sys.exit('no vendored Sample.plist; pass one or run tools/fetch_oc.py')

    profiles = Path(a.profiles)
    sample = ocgen.load_plist(a.sample)
    paths = sorted(glob.glob(f'{ocgen.CONFIG_ROOT}/**/*.plist', recursive=True))
    if a.rehash:
        return rehash(sample, profiles)
    if not paths:
        return against_catalogue(sample, profiles, a.comments)
    ok, bad = 0, []
    for p in paths:
        row = ocgen.classify(p)
        built = ocgen.assemble(sample, ocgen.layer_chain(row, profiles),
                               ocgen.build_params(row))
        disk = ocgen.load_plist(p)
        if ocgen.canonical_bytes(disk, a.comments) == ocgen.canonical_bytes(built, a.comments):
            ok += 1
            continue
        want, got = ocgen.comparable(disk, a.comments), ocgen.comparable(built, a.comments)
        keys = ([f'{k}  (only on disk)' for k in sorted(set(want) - set(got))]
                + [f'{k}  (only generated)' for k in sorted(set(got) - set(want))]
                + [f'{k}  {want[k]} != {got[k]}'
                   for k in sorted(set(want) & set(got)) if want[k] != got[k]])
        bad.append((p, keys or ['(structure differs but no scalar does)']))

    for p, keys in bad:
        print(f'MISMATCH {p}')
        for k in keys[:8]:
            print(f'    {k}')
        if len(keys) > 8:
            print(f'    ... +{len(keys) - 8} more')
    print(f'\n  {ok}/{len(paths)} configs reproduced'
          f'{" (Comment strings included)" if a.comments else ""}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
