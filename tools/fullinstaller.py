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


def offered(g):
    """The newest build of each macOS that runs on Intel, newest first.

    [{'name', 'version', 'build', 'size', 'product', 'prod'}]; 'prod' is the
    tool's own record, which is what downloading takes."""
    names = {v: k.title() for k, v in g.version_names.items()}
    best = {}
    for p in g.mac_prods:
        if INTEL not in [d.lower() for d in p.get('device_ids', [])]:
            continue
        v = (p.get('version') or '').strip()
        # 10.15 is a release of its own; from 11 on the first number is
        major = '.'.join(v.split('.')[:2]) if v.startswith('10.') else v.split('.')[0]
        if major not in names:
            continue
        key = tuple(int(x) for x in v.split('.') if x.isdigit())
        if major not in best or key > best[major][0]:
            best[major] = (key, p)
    rows = []
    for major, (_, p) in best.items():
        rows.append({'name': names[major], 'major': major,
                     'version': p['version'].strip(), 'build': p.get('build', ''),
                     'size': sum(x.get('Size') or 0 for x in p.get('packages', [])) or -1, 'product': p['product'], 'prod': p})
    rows.sort(key=lambda r: tuple(int(x) for x in r['major'].split('.')), reverse=True)
    return rows


def find(rows, wanted):
    wanted = (wanted or '').strip().lower()
    for r in rows:
        if wanted in (r['name'].lower(), r['major'], r['version'], r['product'].lower()):
            return r
    return None


def size_text(size):
    if not isinstance(size, (int, float)) or size <= 0:
        return 'size unknown'
    return f'{size / 1e9:.1f} GB'


def fetch(g, row, into, every=2.0):
    """Download one product into <into>. Returns (files, complaint).

    The downloader resumes a partial file, so asking again after a dropped
    connection picks up where it stopped rather than starting the 13 GB over."""
    into = Path(into)
    into.mkdir(parents=True, exist_ok=True)
    g.download_dir = str(into)
    progress = recovery.Progress(every=every)
    try:
        with contextlib.redirect_stdout(progress), \
                contextlib.redirect_stderr(progress):
            g.download_prod(row['prod'])
    except Exception as exc:  # the tool's own ProgramError, or the network's
        progress.close()
        return [], str(exc).strip() or type(exc).__name__
    progress.close()
    files = sorted(p for p in into.iterdir() if p.is_file())
    return files, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--list', action='store_true', help='what Apple serves for Intel Macs')
    ap.add_argument('--macos', help='a name or a version, as --list prints them')
    ap.add_argument('--out', default='.', help='where the package goes')
    ap.add_argument('--work', default=None, help='where the tool keeps its catalog')
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
            print(f"  {r['name']:14} {r['version']:10} {r['build']:10} {size_text(r['size'])}")
        print(f'\n  Read from Apple\'s catalog by gibMacOS {version()}.')
        return 0
    row = find(rows, a.macos)
    if not row:
        print(f'  {a.macos}: Apple\'s catalog has no installer by that name for Intel Macs')
        return 1
    print(f"  {row['name']} {row['version']} ({row['build']}), {size_text(row['size'])}")
    files, complaint = fetch(g, row, a.out)
    if complaint:
        print(f'  {complaint}')
        return 1
    for f in files:
        print(f'  {f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
