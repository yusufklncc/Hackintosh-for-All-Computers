"""Pick the AirportItlwm build that matches a macOS release, fetching if needed.

Intel Wi-Fi is the one device where no single kext covers every macOS: the kext
is compiled against each release's AirPort interface and published as a separate
15 MB download. Vendoring all eight would add well over a hundred megabytes to a
repository whose whole release is a fraction of that, and an EFI can only carry
one of them anyway.

So the newest is vendored and works offline, and any other release is downloaded
once into a cache. A build that needs a variant it cannot reach says so and
carries on without Wi-Fi rather than shipping the wrong binary.
"""
import os
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

CACHE = Path(os.environ.get('ITLWM_CACHE', '.itlwm-cache'))
VENDORED = Path('EFI/OC/Kexts/AirportItlwm.kext')


def variant_set():
    for s in ocgen.read_toml(Path('data/network.toml')).get('variant_set', []):
        if s['role'] == 'wifi':
            return s
    return None


def pick(darwin, minor=None):
    """The asset name for a Darwin major, or None if the project has no build.

    Sonoma is the awkward one: 14.4 changed the interface again, so it has two
    builds. Without a minor version the later one is the safer default, since
    14.4 and up is where a new install lands."""
    s = variant_set()
    if not s:
        return None
    hits = [v for v in s['variant'] if v['min_darwin'] <= darwin <= v['max_darwin']]
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0]['asset']
    if darwin == 23 and minor is not None:
        return 'Sonoma14.0' if minor < 4 else 'Sonoma14.4'
    return hits[-1]['asset']


def resolve(darwin, minor=None, allow_download=True):
    """(path to the kext to use, note) - path is None when it cannot be had."""
    s = variant_set()
    asset = pick(darwin, minor)
    if not asset:
        return None, (f"{s['project']} {s['release']} publishes no build for "
                      f"darwin {darwin}")
    if asset == s['vendored']:
        return VENDORED, f'{asset}, vendored'
    cached = CACHE / f'{s["release"]}-{asset}' / 'AirportItlwm.kext'
    if cached.exists():
        return cached, f'{asset}, from cache'
    if not allow_download:
        return None, f'{asset} is not vendored and downloading is off'
    url = (f'https://github.com/{s["project"]}/releases/download/{s["release"]}'
           f'/AirportItlwm_{s["release"]}_stable_{asset}.kext.zip')
    dest = cached.parent
    try:
        dest.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix('.zip')
        urllib.request.urlretrieve(url, tmp)
        with zipfile.ZipFile(tmp) as z:
            z.extractall(dest)
        tmp.unlink()
    except (urllib.error.URLError, OSError, zipfile.BadZipFile) as exc:
        shutil.rmtree(dest, ignore_errors=True)
        return None, f'{asset} could not be downloaded ({type(exc).__name__})'
    # the zip may nest the kext a level down
    if not cached.exists():
        found = [p for p in dest.rglob('AirportItlwm.kext') if '__MACOSX' not in str(p)]
        if not found:
            return None, f'{asset} download did not contain the kext'
        return found[0], f'{asset}, downloaded'
    return cached, f'{asset}, downloaded'


if __name__ == '__main__':
    for darwin, minor in ((23, 4), (23, 0), (22, None), (19, None), (24, None), (16, None)):
        path, note = resolve(darwin, minor, allow_download=False)
        print(f'  darwin {darwin}' + (f'.{minor}' if minor is not None else '   ')
              + f'  -> {note}' + (f'   {path}' if path else ''))
