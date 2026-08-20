"""Download and cache an OpenCore release, then print the paths inside it.

Every release ships the pieces the generator needs: the canonical Sample.plist
for that exact version, the EFI skeleton, and matching ocvalidate / macserial
binaries. Pinning the version pins all of them together.

    python3 tools/fetch_oc.py 1.0.5
    python3 tools/fetch_oc.py latest --what sample
"""
import argparse
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

API = 'https://api.github.com/repos/acidanthera/OpenCorePkg/releases'
CACHE = Path(os.environ.get('OC_CACHE', '.oc-cache'))


def resolve(version):
    url = f'{API}/latest' if version == 'latest' else f'{API}/tags/{version}'
    with urllib.request.urlopen(url) as r:
        rel = json.load(r)
    if 'tag_name' not in rel:
        sys.exit(f'no such OpenCore release: {version}')
    asset = next((a for a in rel['assets']
                  if a['name'] == f"OpenCore-{rel['tag_name']}-RELEASE.zip"), None)
    if not asset:
        sys.exit(f"release {rel['tag_name']} has no RELEASE zip")
    return rel['tag_name'], asset['browser_download_url']


def fetch(version):
    tag, url = resolve(version)
    dest = CACHE / tag
    if not (dest / 'Docs' / 'Sample.plist').exists():
        dest.mkdir(parents=True, exist_ok=True)
        zpath = CACHE / f'OpenCore-{tag}-RELEASE.zip'
        if not zpath.exists():
            urllib.request.urlretrieve(url, zpath)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(dest)
        for tool in ('ocvalidate/ocvalidate', 'macserial/macserial'):
            p = dest / 'Utilities' / tool
            if p.exists():
                p.chmod(0o755)
    return tag, dest


PATHS = {
    'root':       lambda d: d,
    'sample':     lambda d: d / 'Docs' / 'Sample.plist',
    'efi':        lambda d: d / 'X64' / 'EFI',
    'ocvalidate': lambda d: d / 'Utilities' / 'ocvalidate' / 'ocvalidate',
    'macserial':  lambda d: d / 'Utilities' / 'macserial' / 'macserial',
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('version', nargs='?', default='latest')
    ap.add_argument('--what', choices=sorted(PATHS), default='sample')
    a = ap.parse_args()
    tag, dest = fetch(a.version)
    print(PATHS[a.what](dest))


if __name__ == '__main__':
    main()
