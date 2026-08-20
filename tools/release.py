"""Build every published config and zip each one for a release.

    python3 tools/release.py --out dist
    python3 tools/release.py --out dist --limit 3     # smoke test

One zip per catalogue entry, each holding only what that config references. A
single failure fails the run: a release that quietly skips a config is worse
than no release.
"""
import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

PROFILES = Path('profiles')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='dist')
    ap.add_argument('--work', default='build/release')
    ap.add_argument('--limit', type=int, help='build only the first N (smoke test)')
    a = ap.parse_args()

    entries = ocgen.read_toml(PROFILES / 'catalogue.toml')['config']
    if a.limit:
        entries = entries[:a.limit]
    out, work = Path(a.out), Path(a.work)
    out.mkdir(parents=True, exist_ok=True)
    if work.exists():
        shutil.rmtree(work)

    failed, total = [], 0
    for e in entries:
        stage = work / e['name']
        r = subprocess.run([sys.executable, 'tools/build.py', '--name', e['name'],
                            '--out', str(stage / 'EFI')], capture_output=True, text=True)
        if r.returncode != 0:
            failed.append((e['name'], (r.stdout + r.stderr).strip()))
            continue
        zpath = out / (e['name'].replace('/', ' - ') + '.zip')
        with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in sorted(stage.rglob('*')):
                if f.is_file():
                    z.write(f, f.relative_to(stage))
        total += zpath.stat().st_size
        shutil.rmtree(stage)

    print(f'  {len(entries) - len(failed)}/{len(entries)} built, '
          f'{total / 1048576:.0f} MB of zips in {out}')
    for name, log in failed:
        print(f'::error::{name}')
        print(log)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
