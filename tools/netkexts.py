"""Turn detected network hardware into kext entries for a config.

Two modes, because both are reasonable:

  every supported macOS   add each kext with the Darwin bounds its documentation
                          gives, and let OpenCore load whichever applies. One EFI
                          that boots any version the hardware supports.

  one macOS               add only the kexts whose range covers that release.
                          Fewer kexts, nothing loaded that will never apply.

Neither invents a bound. They all come from data/network.toml, which quotes the
project that published the rule.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

DATA = Path('data')


def releases():
    return ocgen.read_toml(DATA / 'macos.toml')['release']


def sets():
    return ocgen.read_toml(DATA / 'network.toml')['set']


def _ver(v):
    return tuple(int(x) for x in v.split('.')) if v else None


def covers(kext, darwin):
    """Does this kext apply on that Darwin major?"""
    lo, hi = _ver(kext.get('min_kernel')), _ver(kext.get('max_kernel'))
    if lo and darwin < lo[0]:
        return False
    if hi and darwin > hi[0]:
        return False
    return True


def entries(matched_kexts, darwin=None):
    """Config Kernel.Add entries for the sets whose match kext was detected.

    darwin=None means every supported macOS: keep the bounds and add everything.
    A number means one release: drop what cannot apply and drop the bounds with
    it, since they no longer carry information."""
    out, chosen = [], []
    for s in sets():
        if s['match'] not in matched_kexts:
            continue
        picked = []
        for k in s['kext']:
            if darwin is not None and not covers(k, darwin):
                continue
            e = {'Arch': 'x86_64', 'BundlePath': k['bundle'],
                 'Comment': s['label'], 'Enabled': True,
                 'ExecutablePath': '', 'MaxKernel': '', 'MinKernel': '',
                 'PlistPath': 'Contents/Info.plist'}
            if darwin is None:
                e['MinKernel'] = k.get('min_kernel', '')
                e['MaxKernel'] = k.get('max_kernel', '')
            picked.append((e, k))
        if picked:
            chosen.append((s, [k for _, k in picked]))
            out += [e for e, _ in picked]
    return out, chosen


def fill_executables(entries_list, kexts_dir=Path('EFI/OC/Kexts')):
    """A codeless kext has no binary; look rather than assume."""
    import plistlib
    for e in entries_list:
        info = kexts_dir / e['BundlePath'] / 'Contents' / 'Info.plist'
        exe = ''
        if info.exists():
            with open(info, 'rb') as fh:
                name = plistlib.load(fh).get('CFBundleExecutable')
            if name and (kexts_dir / e['BundlePath'] / 'Contents' / 'MacOS' / name).exists():
                exe = f'Contents/MacOS/{name}'
        e['ExecutablePath'] = exe
    return entries_list


if __name__ == '__main__':
    have = {'IntelMausi.kext', 'IntelBluetoothFirmware.kext'}
    for label, darwin in (('every supported macOS', None), ('Sonoma (darwin 23)', 23),
                          ('Big Sur (darwin 20)', 20), ('Yosemite (darwin 14)', 14)):
        out, chosen = entries(have, darwin)
        fill_executables(out)
        print(f'\n  {label}: {len(out)} kexts')
        for e in out:
            rng = f"{e['MinKernel'] or '-':>9s} .. {e['MaxKernel'] or '-'}"
            print(f"      {e['BundlePath']:30s} {rng:22s} exec={'yes' if e['ExecutablePath'] else 'codeless'}")
