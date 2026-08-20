"""Measure which OpenCore versions each profile is valid against.

Rather than guessing an oc_min/oc_max per profile, build every profile against
each OpenCore release's own Sample.plist and run that release's own ocvalidate.
The answer is then observed rather than asserted.

    OC_CACHE=.oc-cache python3 tools/matrix.py 0.9.5 1.0.0 1.0.5 1.0.7
"""
import argparse
import os
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

CACHE = Path(os.environ.get('OC_CACHE', '.oc-cache'))
PROFILES = Path('profiles')


def targets():
    """One representative build per cpu profile."""
    out = []
    for p in sorted(PROFILES.glob('cpu/*/*.toml')):
        name = p.stem
        if '.' in name:
            continue
        plat = p.parent.name
        platform, _, vendor = plat.partition('-')
        cores = 8 if vendor == 'amd' else None
        out.append(dict(path='', platform=platform, vendor=vendor or None, cpu=name,
                        chipset=None, oem=None, variant=None, cores=cores))
    return out


def tool(version, name):
    import platform as _p
    sfx = {'Darwin': '', 'Linux': '.linux', 'Windows': '.exe'}[_p.system()]
    p = CACHE / version / 'Utilities' / name / (name + sfx)
    if p.exists():
        p.chmod(0o755)
    return p if p.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('versions', nargs='+')
    ap.add_argument('-v', '--verbose', action='store_true')
    ap.add_argument('--write', action='store_true',
                    help='record the measured range in profiles/support.toml')
    a = ap.parse_args()

    rows = targets()
    results = {}
    for ver in a.versions:
        sample_p = CACHE / ver / 'Docs' / 'Sample.plist'
        ocv = tool(ver, 'ocvalidate')
        if not sample_p.exists() or not ocv:
            print(f'  {ver}: not cached, run tools/fetch_oc.py {ver}')
            continue
        sample = ocgen.load_plist(sample_p)
        for row in rows:
            key = f"{row['platform']}-{row['vendor'] or ''}/{row['cpu']}"
            try:
                cfg = ocgen.assemble(sample, ocgen.layer_chain(row, PROFILES),
                                     ocgen.build_params(row))
                # a real build mints these; without them ocvalidate reports the
                # missing keys rather than anything about the profile
                cfg['PlatformInfo']['Generic'].update(
                    SystemSerialNumber='W00000000001', MLB='W00000000000000001',
                    SystemUUID='00000000-0000-0000-0000-000000000001',
                    ROM=b'\x11\x22\x33\x44\x55\x66')
                with tempfile.NamedTemporaryFile('wb', suffix='.plist', delete=False) as fh:
                    plistlib.dump(cfg, fh, sort_keys=False)
                    tmp = fh.name
                r = subprocess.run([str(ocv), tmp], capture_output=True, text=True)
                os.unlink(tmp)
                ok = 'No issues found' in r.stdout
                note = '' if ok else r.stdout
            except Exception as exc:
                ok, note = False, f'{type(exc).__name__}: {exc}'
            results[(key, ver)] = (ok, note)

    keys = sorted({k for k, _ in results})
    vers = [v for v in a.versions if any((k, v) in results for k in keys)]
    width = max(len(k) for k in keys)
    print(f'  {"profile":{width}s} ' + ' '.join(f'{v:>6s}' for v in vers))
    for k in keys:
        cells = ' '.join(f'{"ok" if results[(k, v)][0] else "FAIL":>6s}'
                         if (k, v) in results else f'{"-":>6s}' for v in vers)
        print(f'  {k:{width}s} {cells}')

    if a.write:
        per = {}
        for k in keys:
            good = [v for v in vers if results.get((k, v), (False,))[0]]
            if good:
                per[k] = {'oc_min': good[0], 'tested': good}
        shared = {kk: vv for kk, vv in per.items()}
        common = sorted({tuple(v['tested']) for v in shared.values()})
        out = {'default': {'oc_min': min(v['oc_min'] for v in shared.values()),
                           'oc_max': '',
                           'tested': list(common[0]) if len(common) == 1 else []}}
        if len(common) > 1:
            out['profile'] = shared
        ocgen.write_toml(PROFILES / ocgen.SUPPORT, out,
                         '# OpenCore versions every profile was observed to validate against.\n'
                         '# Measured by tools/matrix.py, not asserted. oc_max empty means no\n'
                         '# upper bound was found; the newest version tested is the last in\n'
                         '# "tested". extract.py never rewrites this file.\n')
        print(f'\n  wrote {PROFILES / ocgen.SUPPORT}')

    fails = {(k, v): n for (k, v), (ok, n) in results.items() if not ok}
    print(f'\n  {len(results) - len(fails)}/{len(results)} combinations valid')
    if fails and a.verbose:
        seen = set()
        for (k, v), note in sorted(fails.items()):
            first = note.strip().splitlines()[:4]
            sig = tuple(first)
            if sig in seen:
                continue
            seen.add(sig)
            print(f'\n  {k} @ {v}')
            for line in first:
                print(f'      {line}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
