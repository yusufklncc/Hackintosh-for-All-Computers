"""Check that every kext is listed after the ones it needs.

This is not a rule anybody here invented. OpenCore's own reference manual says
it, and says where to read the answer from:

    "The load order is based on the order in which the kexts appear in the
     array. Hence, dependencies must appear before kexts that depend on them."

    "To track the dependency order, inspect the OSBundleLibraries key in the
     Info.plist file of the kext being added. Any kext included under the key is
     a dependency that must appear before the kext being added."

    "Kexts may have inner kexts (Plugins) included in the bundle. Such Plugins
     must be added separately and follow the same global ordering rules as other
     kexts."

So the graph is read out of the kexts, exactly as instructed, and nothing about
which kext needs which is written down here. A config that fails this does not
fail loudly at boot: the dependent kext simply does not load, and whatever it
was for does not work.

    python3 tools/kextorder.py                    # every published config
    python3 tools/kextorder.py path/to/config.plist
"""
import argparse
import os
import plistlib
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

KEXTS = Path('EFI/OC/Kexts')

BOLD, DIM, GREEN, RED, RESET = '\033[1m', '\033[2m', '\033[32m', '\033[31m', '\033[0m'
if os.environ.get('NO_COLOR') or not sys.stdout.isatty():
    BOLD = DIM = GREEN = RED = RESET = ''


def graph(root=KEXTS):
    """{bundle path: {bundle paths it needs}} from the kexts themselves.

    A plugin is a bundle path of its own - `VoodooRMI.kext/Contents/PlugIns/
    RMISMBus.kext` - because that is how OpenCore refers to it and how the
    manual says to treat it."""
    root = Path(root)
    ids, declared = {}, {}
    for info in sorted(root.rglob('Contents/Info.plist')):
        bundle = str(info.parent.parent.relative_to(root))
        try:
            with open(info, 'rb') as fh:
                plist = plistlib.load(fh)
        except (OSError, plistlib.InvalidFileException):
            continue
        ids[plist.get('CFBundleIdentifier', '')] = bundle
        # the 64-bit list is separate in older bundles and means the same thing
        declared[bundle] = set(plist.get('OSBundleLibraries') or {}) | set(
            plist.get('OSBundleLibraries_x86_64') or {})
    return {b: {ids[i] for i in want if i in ids} - {b}
            for b, want in declared.items()}


def check(entries, deps=None):
    """[(bundle, needed, why)] for every enabled kext listed too early.

    Only the enabled ones: a kext that is off does not load, so it cannot
    satisfy anything and cannot be waiting on anything."""
    deps = graph() if deps is None else deps
    order = [e['BundlePath'] for e in entries if e.get('Enabled')]
    where = {}
    for i, bundle in enumerate(order):
        where.setdefault(bundle, i)
    problems = []
    for i, bundle in enumerate(order):
        for needed in sorted(deps.get(bundle, ())):
            if needed not in where:
                problems.append((bundle, needed, 'is not in the config'))
            elif where[needed] > i:
                problems.append((bundle, needed, f'is listed after it, at '
                                                 f'{where[needed] + 1} not before '
                                                 f'{i + 1}'))
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('config', nargs='?', help='a config.plist to check')
    a = ap.parse_args(argv)

    deps = graph()
    if a.config:
        cfg = ocgen.load_plist(Path(a.config))
        problems = check(cfg['Kernel']['Add'], deps)
        for bundle, needed, why in problems:
            print(f'  {RED}{bundle}{RESET} needs {needed}, which {why}')
        print(f'  {"no ordering problems" if not problems else str(len(problems)) + " problems"}'
              f' in {a.config}')
        return 1 if problems else 0

    import verify
    sample = ocgen.load_plist(ocgen.vendored_sample())
    profiles = Path('profiles')
    entries = ocgen.read_toml(profiles / 'catalogue.toml')['config']
    seen = {}
    for e in entries:
        row = verify._row(e)
        cfg = ocgen.assemble(sample, ocgen.layer_chain(row, profiles),
                             ocgen.build_params(row))
        for bundle, needed, why in check(cfg['Kernel']['Add'], deps):
            seen.setdefault((bundle, needed, why), []).append(e['name'])
    linked = sum(1 for v in deps.values() if v)
    print(f'{BOLD}Kext load order{RESET}  {DIM}{linked} of {len(deps)} bundles '
          f'declare a dependency{RESET}\n')
    for (bundle, needed, why), names in sorted(seen.items(), key=lambda x: -len(x[1])):
        print(f'  {RED}{len(names):3d}{RESET}  {bundle} needs {needed}, which {why}')
        print(f'       e.g. {names[0]}')
    if not seen:
        print(f'  {GREEN}{len(entries)} published configs, every dependency listed '
              f'before the kext that needs it{RESET}')
    return 1 if seen else 0


if __name__ == '__main__':
    sys.exit(main())
