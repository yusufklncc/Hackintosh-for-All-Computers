"""Package a release: one shared EFI, plus a config.plist per published config.

    python3 tools/release.py --out dist

Every EFI in this repository carries the same binaries; only the config.plist
differs, and OpenCore loads nothing the config does not name. So the release is
two files rather than one per config:

    EFI-base.zip   the EFI folder, everything except OC/config.plist
    configs.zip    one config.plist per published config, under its own name

That is about 15 MB instead of the gigabyte that shipping 179 near-identical
copies would cost.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

PROFILES = Path('profiles')
SRC = Path('EFI')


def zip_base(dest):
    """The whole EFI payload, so any config in configs.zip can run on it."""
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(SRC.rglob('*')):
            if f.is_file():
                z.write(f, Path('EFI') / f.relative_to(SRC))
    return dest.stat().st_size


def zip_configs(dest, entries, work):
    """One config.plist per catalogue entry, at the path its name describes."""
    failed = []
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for e in entries:
            stage = work / 'one'
            if stage.exists():
                shutil.rmtree(stage)
            r = subprocess.run([sys.executable, 'tools/build.py', '--name', e['name'],
                                '--out', str(stage / 'EFI')], capture_output=True, text=True)
            cfg = stage / 'EFI' / 'OC' / 'config.plist'
            if r.returncode != 0 or not cfg.exists():
                failed.append((e['name'], (r.stdout + r.stderr).strip()))
                continue
            z.write(cfg, f"{e['name']}.plist")
    return dest.stat().st_size, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='dist')
    ap.add_argument('--limit', type=int, help='only the first N configs (smoke test)')
    a = ap.parse_args()

    entries = ocgen.read_toml(PROFILES / 'catalogue.toml')['config']
    if a.limit:
        entries = entries[:a.limit]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    base = zip_base(out / 'EFI-base.zip')
    with tempfile.TemporaryDirectory() as tmp:
        cfgs, failed = zip_configs(out / 'configs.zip', entries, Path(tmp))

    print(f'  EFI-base.zip   {base / 1048576:5.1f} MB')
    print(f'  configs.zip    {cfgs / 1048576:5.1f} MB   '
          f'{len(entries) - len(failed)}/{len(entries)} configs')
    for name, log in failed:
        print(f'::error::{name}')
        print(log)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
