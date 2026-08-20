"""Equivalence gate.

Regenerates every config under EFI/OC/config from the profile set and compares
it against the file on disk. Generated identity (serial, MLB, UUID, ROM) is
excluded because a profile never stores it; Comment strings are excluded by
default because they carry no runtime meaning.

Nothing in EFI/OC/config may be deleted until this reports 179/179.

    python3 tools/verify.py <Sample.plist> [--profiles profiles] [--comments]
"""
import argparse
import glob
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sample')
    ap.add_argument('--profiles', default='profiles')
    ap.add_argument('--comments', action='store_true', help='also require Comment strings to match')
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args()

    profiles = Path(a.profiles)
    sample = ocgen.load_plist(a.sample)
    paths = sorted(glob.glob(f'{ocgen.CONFIG_ROOT}/**/*.plist', recursive=True))
    ok, bad = 0, []
    for p in paths:
        row = ocgen.classify(p)
        built = ocgen.assemble(sample, ocgen.layer_chain(row, profiles))
        want = ocgen.comparable(ocgen.load_plist(p), a.comments)
        got = ocgen.comparable(built, a.comments)
        if want == got:
            ok += 1
            continue
        keys = sorted(set(want) ^ set(got)) + sorted(k for k in set(want) & set(got) if want[k] != got[k])
        bad.append((p, keys))

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
