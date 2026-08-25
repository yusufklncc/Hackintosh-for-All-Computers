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
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

API = 'https://api.github.com/repos/acidanthera/OpenCorePkg/releases'
CACHE = Path(os.environ.get('OC_CACHE', '.oc-cache'))


def _get(url):
    """Read a URL, however this machine can.

    urllib carries its own trust store and a network that inspects TLS refuses
    it; curl uses the system's. Same fallback as the other fetchers here."""
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.read()
    except urllib.error.URLError as first:
        import shutil
        import subprocess
        if not shutil.which('curl'):
            raise
        got = subprocess.run(['curl', '-sSL', '--max-time', '300', url],
                             capture_output=True)
        if got.returncode != 0 or not got.stdout:
            raise SystemExit(f'{first}\nand curl: {got.stderr.decode()[:200]}')
        return got.stdout


def resolve(version):
    url = f'{API}/latest' if version == 'latest' else f'{API}/tags/{version}'
    rel = json.loads(_get(url))
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
            zpath.write_bytes(_get(url))
        with zipfile.ZipFile(zpath) as z:
            z.extractall(dest)
        # every build of them, not only the one with no extension. The Linux
        # ones came out of the zip unexecutable, were vendored that way, and
        # the build that shells out to them stopped dead.
        for tool in ('ocvalidate', 'macserial'):
            for built in (dest / 'Utilities' / tool).glob(f'{tool}*'):
                if built.is_file() and built.suffix != '.exe':
                    built.chmod(0o755)
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
