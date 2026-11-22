"""Apple's full macOS installer package, fetched with gibMacOS.

Recovery is enough when the machine can reach Apple during the install. When it
cannot - no Wi-Fi macOS drives, and no Ethernet either - the whole installer has
to be on the stick, and that is InstallAssistant.pkg: 13 GB or more, served by
Apple's own software update catalog. corpnewt's gibMacOS reads that catalog and
downloads from it. It is vendored here (MIT, pinned in vendor/tools.lock) and
driven in this process, the way SSDTTime is.

Nothing of Apple's is redistributed. The package comes from Apple's server to
the person's own disk; this repository only knows where to ask.

    python3 tools/fullinstaller.py --list
    python3 tools/fullinstaller.py --macos sequoia --out ~/Downloads/macOS

Only installers that run on an Intel Mac are offered: the catalog says which
models each one is for, and a build that names no x86 board is Apple silicon
only and will not install on anything this builds an EFI for.
"""
import argparse
import contextlib
import importlib.util
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sysenv  # noqa: F401,E402
import ocgen  # noqa: E402
import recovery  # noqa: E402

VENDOR = Path('vendor/tools/gibMacOS')
LOCK = Path('vendor/tools.lock')
# what gibMacOS itself passes to say "any Intel Mac": the virtual machine board,
# which Apple lists for every installer that runs on x86_64
INTEL = 'vmm-x86_64'


def version():
    return ocgen.read_toml(LOCK)['tool']['gibMacOS']['version']


def prepare(work):
    """A copy of the tool somewhere writable.

    gibMacOS keeps its catalog, its settings and a product cache beside its own
    source. Inside a .app, or a folder Windows put under Program Files, that is
    not writable - and writing into a signed bundle breaks the signature."""
    work = Path(work)
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(VENDOR, work)
    return work


def load(work):
    """Import gibMacOS from the working copy.

    It and SSDTTime both import a package called `Scripts`, and whichever was
    imported first would answer for both. Clearing it first means this one gets
    its own."""
    for name in [n for n in sys.modules if n == 'Scripts' or n.startswith('Scripts.')
                 or n == 'gibMacOS']:
        del sys.modules[name]
    sys.path.insert(0, str(work))
    try:
        spec = importlib.util.spec_from_file_location('gibMacOS', Path(work) / 'gibMacOS.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(work))
    return module


def catalog(work):
    """(gibMacOS instance, complaint). The instance has read Apple's catalog."""
    module = load(prepare(work))
    g = module.gibMacOS(interactive=False)
    try:
        with contextlib.redirect_stderr(open(os.devnull, 'w')):
            g.set_prods()
    except module.ProgramError as exc:
        return None, str(exc).strip()
    except OSError as exc:
        return None, f'Apple\'s catalog could not be read: {exc}'
    return g, None


def runs_on_intel(p):
    """Whether an installer in the catalog is one an Intel Mac runs.

    From Big Sur on the catalog says so, by listing the x86 virtual machine
    board among the models. Before Big Sur it lists no models at all - and
    there was no Apple silicon yet, so every one of those is Intel. Reading
    the missing list as "not Intel" is what hid High Sierra to Catalina."""
    ids = [d.lower() for d in p.get('device_ids', [])]
    if INTEL in ids:
        return True
    return (p.get('version') or '').strip().startswith('10.')


def _key(v):
    return tuple(int(x) for x in v.split('.') if x.isdigit())


def _build_key(build):
    """19H15 after 19H4: the number after the letter is a number, not text."""
    import re as _re
    return tuple(int(x) if x.isdigit() else x for x in _re.findall(r'\d+|\D+', build or ''))


def offered(g):
    """Every build Apple serves that runs on Intel, newest first.

    All of them, not one per release: a point release is sometimes the one
    that works on a given machine, and the choice is the person's to make.
    [{'name', 'major', 'version', 'build', 'size', 'product', 'prod',
    'newest'}]; 'prod' is the tool's own record, which downloading takes, and
    'newest' marks the latest build of each release."""
    names = {v: k.title() for k, v in g.version_names.items()}
    rows = []
    for p in g.mac_prods:
        if not runs_on_intel(p):
            continue
        v = (p.get('version') or '').strip()
        # 10.15 is a release of its own; from 11 on the first number is
        major = '.'.join(v.split('.')[:2]) if v.startswith('10.') else v.split('.')[0]
        if major not in names:
            continue
        rows.append({'name': names[major], 'major': major, 'version': v,
                     'build': p.get('build', ''), 'product': p['product'],
                     'size': sum(x.get('Size') or 0 for x in p.get('packages', [])) or -1,
                     'prod': p})
    rows.sort(key=lambda r: (_key(r['version']), _build_key(r['build'])), reverse=True)
    seen = set()
    for r in rows:
        r['newest'] = r['major'] not in seen
        seen.add(r['major'])
    return rows


def find(rows, wanted):
    """A build or a product id picks exactly one row; a name or a release
    number picks the newest build of it."""
    wanted = (wanted or '').strip().lower()
    for r in rows:
        if wanted in (r['build'].lower(), r['product'].lower()):
            return r
    for r in rows:                     # newest first, so the first match is newest
        if wanted in (r['name'].lower(), r['major'], r['version']):
            return r
    return None


def size_text(size):
    if not isinstance(size, (int, float)) or size <= 0:
        return 'size unknown'
    return f'{size / 1e9:.1f} GB'


def _amount(n):
    return f'{n / 1e9:.2f} GB' if n >= 1e8 else f'{n / 1e6:.1f} MB'


class Watch:
    """How far one file has got, said every few seconds from a thread here.

    The tool draws its own progress bar from a second *process*. In a frozen
    build that process is the engine started again - PyInstaller re-runs the
    program for it, and without freeze_support() that is a second builder
    parsing arguments it was never given. A thread reading the file's size
    needs none of that, and its lines are whole ones a window can show."""

    def __init__(self, say, every):
        import threading
        self.say, self.every = say, every
        self.path, self.total, self.start_at = None, 0, 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def begin(self, path, total):
        self.path, self.total = Path(path), total
        self.start_at = self.path.stat().st_size if self.path.exists() else 0
        self.t0 = time.monotonic()
        name = self.path.name
        if 0 < self.start_at < total:
            self.say(f'{name}: resuming at {_amount(self.start_at)} of {_amount(total)}')
        elif total and self.start_at >= total:
            self.say(f'{name}: already here, {_amount(total)}')
        else:
            self.say(f'{name}: {_amount(total)}' if total else name)
        if not self.thread.is_alive():
            self.thread.start()

    def line(self):
        if not self.path or not self.path.exists() or self.total < 1e8:
            return None
        have = self.path.stat().st_size
        rate = (have - self.start_at) / max(time.monotonic() - self.t0, 1e-3)
        left = (self.total - have) / rate if rate > 0 else 0
        when = (f', about {left / 3600:.1f} h left' if left >= 3600 else
                f', about {left / 60:.0f} min left' if left >= 60 else '')
        return (f'{self.path.name}: {have / 1e9:.2f} of {self.total / 1e9:.2f} GB, '
                f'{rate / 1e6:.1f} MB/s{when}')

    def _run(self):
        while not self.stop.wait(self.every):
            said = self.line()
            if said:
                self.say(said)


def fetch(g, row, into, every=2.0):
    """Download one product into <into>. Returns (files, complaint).

    One connection, as the tool makes it. A partial file is resumed with an
    HTTP Range request and a finished one is skipped by its size, so pressing
    the button again after the window closed - same build, same folder -
    carries on rather than starting the 13 GB over."""
    into = Path(into)
    into.mkdir(parents=True, exist_ok=True)
    g.download_dir = str(into)
    sizes = {pkg['URL']: pkg.get('Size') or 0 for pkg in row['prod'].get('packages', [])}
    progress = recovery.Progress(every=every)
    watch = Watch(progress.say, every)
    original = g.d.stream_to_file

    def stream(url, file_path, *args, **kwargs):
        kwargs['progress'] = False          # no second process; see Watch
        watch.begin(file_path, sizes.get(url, 0))
        return original(url, file_path, *args, **kwargs)

    g.d.stream_to_file = stream
    try:
        with contextlib.redirect_stdout(progress), \
                contextlib.redirect_stderr(progress):
            g.download_prod(row['prod'])
    except Exception as exc:  # the tool's own ProgramError, or the network's
        return [], (str(exc).strip() or type(exc).__name__) + (
            '. What was downloaded is kept: run it again and it resumes.')
    finally:
        watch.stop.set()
        g.d.stream_to_file = original
        progress.close()
    files = sorted(p for p in into.iterdir() if p.is_file())
    return files, None


# --- checking what arrived --------------------------------------------------
#
# Apple's catalog gives every package an IntegrityDataURL: a chunklist, the
# same CNKL format as BaseSystem.chunklist - a SHA-256 for each 10 MB of the
# file. gibMacOS does not use it; this does. Most carry signature method 2,
# where the file ends in a SHA-256 of itself rather than Apple's RSA signature,
# so what it proves is that the bytes match what Apple's catalog points at -
# fetched over HTTPS from the address the HTTPS catalog gave. That catches a
# damaged or swapped download. Authenticity is the package's own Apple
# signature, which the installer checks before it runs anything.
#
# macrecovery reads the same format but refuses method 2 outright, as it
# should for what it does; so the reading is done here, against the same
# struct layout it uses.

import hashlib as _hashlib
import struct as _struct
import urllib.request as _request

CNKL = _struct.Struct('<4sIBBBxQQQ')
CHUNK = _struct.Struct('<I32s')


def chunks(data):
    """[(size, sha256)] from a chunklist's bytes, or raise on anything off."""
    if len(data) < CNKL.size:
        raise ValueError('shorter than a chunklist header')
    magic, size, version, method, signed, count, offset, sig_at = CNKL.unpack_from(data)
    if magic != b'CNKL' or size != CNKL.size or version != 1 or method != 1 \
            or offset != CNKL.size or sig_at != offset + CHUNK.size * count or not count:
        raise ValueError('not a chunklist this understands')
    body = data[:sig_at]
    out = [CHUNK.unpack_from(data, offset + i * CHUNK.size) for i in range(count)]
    tail = data[sig_at:]
    if signed == 2:
        if tail != _hashlib.sha256(body).digest():
            raise ValueError('the chunklist does not match its own digest')
    elif signed == 1:
        if len(tail) != 256:
            raise ValueError('the chunklist signature is the wrong length')
    else:
        raise ValueError(f'unknown signature method {signed}')
    return out


def _get(url, headers=None):
    req = _request.Request(url, headers=dict({'User-Agent': 'hackintosh-fullinstaller'},
                                             **(headers or {})))
    with _request.urlopen(req, timeout=120) as r:
        return r.read()


def bad_chunks(path, listed, say=None, every=200):
    """[(index, offset, size)] of chunks whose SHA-256 is not the listed one.

    A file of the wrong length is reported as every chunk past where it ends."""
    bad, offset = [], 0
    with open(path, 'rb') as f:
        for i, (size, digest) in enumerate(listed):
            block = f.read(size)
            if len(block) != size or _hashlib.sha256(block).digest() != digest:
                bad.append((i, offset, size))
            offset += size
            if say and i and i % every == 0:
                say(f'{Path(path).name}: checked {offset / 1e9:.1f} GB')
        if f.read(1):
            bad.append((len(listed), offset, -1))       # longer than Apple's
    return bad


def check(row, into, say=print, get=_get, repair=True):
    """Check every downloaded package against Apple's integrity data.

    Returns a complaint, or None when all of them check out. A bad chunk is
    downloaded again on its own, by byte range, and checked again - a 15 GB
    package with one damaged 10 MB stretch costs 10 MB, not 15 GB."""
    into = Path(into)
    for pkg in row['prod'].get('packages', []):
        name = pkg['URL'].rsplit('/', 1)[-1]
        path = into / name
        if not path.exists():
            continue
        if pkg.get('IntegrityDataURL'):
            try:
                data = get(pkg['IntegrityDataURL'])
                if pkg.get('IntegrityDataSize') and len(data) != pkg['IntegrityDataSize']:
                    return f'{name}: Apple\'s integrity data is not the size the catalog gives'
                listed = chunks(data)
            except Exception as exc:                 # noqa: BLE001
                return f'{name}: Apple\'s integrity data could not be read ({exc})'
            bad = bad_chunks(path, listed, say)
            if bad and repair:
                if any(size < 0 for _, _, size in bad):
                    with open(path, 'r+b') as f:      # longer than it should be
                        f.truncate(sum(s for s, _ in listed))
                    bad = [b for b in bad if b[2] >= 0]
                say(f'{name}: {len(bad)} of {len(listed)} chunks do not match; '
                    f'downloading only those again')
                with open(path, 'r+b') as f:
                    for i, offset, size in bad:
                        f.seek(offset)
                        f.write(get(pkg['URL'], {'Range': f'bytes={offset}-{offset + size - 1}'}))
                bad = bad_chunks(path, listed)
            if bad:
                return (f'{name}: {len(bad)} of {len(listed)} chunks still do not match '
                        f'Apple\'s integrity data; delete it and download again')
            say(f'{name}: every chunk matches Apple\'s integrity data')
        elif pkg.get('Digest'):
            h = _hashlib.sha1()
            with open(path, 'rb') as f:
                for block in iter(lambda: f.read(1 << 22), b''):
                    h.update(block)
            if h.hexdigest() != pkg['Digest'].lower():
                return f'{name}: does not match the digest in Apple\'s catalog'
            say(f'{name}: matches the digest in Apple\'s catalog')
        elif pkg.get('Size') and path.stat().st_size != pkg['Size']:
            return f'{name}: {path.stat().st_size} bytes where Apple lists {pkg["Size"]}'
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--list', action='store_true', help='what Apple serves for Intel Macs')
    ap.add_argument('--macos', help='a name or a version, as --list prints them')
    ap.add_argument('--out', default='.', help='where the package goes')
    ap.add_argument('--work', default=None, help='where the tool keeps its catalog')
    ap.add_argument('--check', action='store_true',
                    help='only check what is already in --out against Apple\'s integrity data')
    a = ap.parse_args(argv)

    work = Path(a.work) if a.work else Path(a.out) / '.gibmacos'
    g, complaint = catalog(work)
    if not g:
        print(f'  {complaint}')
        return 1
    rows = offered(g)
    if a.list or not a.macos:
        print('Full installers Apple serves for Intel Macs')
        for r in rows:
            print(f"  {r['name']:14} {r['version']:10} {r['build']:10} {size_text(r['size'])}"
                  + ('' if r['newest'] else '   (older build)'))
        print(f'\n  Read from Apple\'s catalog by gibMacOS {version()}.')
        return 0
    row = find(rows, a.macos)
    if not row:
        print(f'  {a.macos}: Apple\'s catalog has no installer by that name for Intel Macs')
        return 1
    print(f"  {row['name']} {row['version']} ({row['build']}), {size_text(row['size'])}")
    if not a.check:
        files, complaint = fetch(g, row, a.out)
        if complaint:
            print(f'  {complaint}')
            return 1
    complaint = check(row, a.out, say=lambda s: print(f'  {s}'))
    if complaint:
        print(f'  {complaint}')
        return 1
    for f in files:
        print(f'  {f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
