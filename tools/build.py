"""Assemble a complete EFI folder from profile coordinates.

    python3 tools/build.py --platform laptop --cpu kaby-lake --oem hp
    python3 tools/build.py --platform desktop --vendor amd --cpu ryzen-threadripper --cores 8
    python3 tools/build.py --list

Everything comes from the repository: the pinned Sample.plist, the profiles, the
kexts, the ACPI tables, the drivers. No step reaches the network.

Only what the generated config actually references is copied, so the output is
the EFI for one machine rather than the whole catalogue.
"""
import argparse
import os
import plistlib
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocgen

SRC = Path('EFI')          # payload that ships with the repository
PROFILES = Path('profiles')


def available():
    out = {}
    for p in sorted(PROFILES.glob('cpu/*/*.toml')):
        plat = p.parent.name
        name = p.stem
        if name.endswith('core') and '.' in name:      # per-core override
            continue
        out.setdefault(plat, []).append(name)
    return out


def row_from_args(a):
    plat = f'{a.platform}-{a.vendor}' if a.vendor else a.platform
    if plat not in available():
        sys.exit(f'unknown platform {plat!r}; try --list')
    if a.cpu not in available()[plat]:
        sys.exit(f'unknown cpu {a.cpu!r} for {plat}; try --list')
    return dict(path='', platform=a.platform, vendor=a.vendor, cpu=a.cpu,
                chipset=a.chipset, oem=a.oem, variant=a.variant, cores=a.cores)


def apply_identity(config, mode, warn):
    gen = config.setdefault('PlatformInfo', {}).setdefault('Generic', {})
    model = gen.get('SystemProductName', '')
    gen['SystemUUID'] = str(uuid.uuid4()).upper()
    # ROM must be this machine's primary MAC address; nothing here can know it.
    gen.setdefault('ROM', bytes.fromhex('112233445566'))
    if mode == 'placeholder':
        gen['SystemSerialNumber'] = gen.get('SystemSerialNumber', '')
        gen['MLB'] = gen.get('MLB', '')
        warn('identity left as a placeholder; set it before signing in to iCloud')
        return
    tool = ocgen.vendored_tool('macserial')
    if not tool:
        warn('macserial not available for this platform; identity left as a placeholder')
        return
    out = subprocess.run([str(tool), '-m', model, '-n', '1'],
                         capture_output=True, text=True)
    line = out.stdout.strip().splitlines()
    if out.returncode != 0 or not line or '|' not in line[0]:
        warn(f'macserial produced nothing for {model!r}; identity left as a placeholder')
        return
    serial, mlb = (x.strip() for x in line[0].split('|', 1))
    gen['SystemSerialNumber'], gen['MLB'] = serial, mlb
    return serial


def copy_payload(config, out, warn, overrides=None, extra_acpi=None):
    """Copy only what the config references, plus the two mandatory binaries.

    overrides maps a bundle name to a path outside EFI/OC/Kexts, which is how a
    downloaded AirportItlwm variant reaches the build without the repository
    having to carry all eight of them."""
    n = 0
    overrides = overrides or {}
    # an SSDT that was just compiled is not in the repository, so it is copied
    # from where it was written rather than looked for under EFI/
    outside = {p.name: p for p in (extra_acpi or [])}

    def take(rel, dest_rel=None):
        nonlocal n
        src, dst = SRC / rel, out / (dest_rel or rel)
        bundle = rel.split('/')[-1]
        if bundle in overrides:
            src = Path(overrides[bundle])
        elif bundle in outside:
            src = outside[bundle]
        if not src.exists():
            warn(f'referenced but missing from the repository: {rel}')
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True) if src.is_dir() else shutil.copy2(src, dst)
        n += 1

    take('BOOT/BOOTx64.efi')
    take('BOOT/.contentFlavour')
    take('OC/OpenCore.efi')
    for e in config['ACPI']['Add']:
        if e.get('Enabled'):
            take(f'OC/ACPI/{e["Path"]}')
    for e in config['Kernel']['Add']:
        if e.get('Enabled'):
            take(f'OC/Kexts/{e["BundlePath"].split("/")[0]}')
    for e in config['UEFI']['Drivers']:
        if e.get('Enabled'):
            take(f'OC/Drivers/{e["Path"]}')
    for e in config['Misc']['Tools']:
        if e.get('Enabled'):
            take(f'OC/Tools/{e["Path"]}')
    if any(d.get('Path') == 'OpenCanopy.efi' and d.get('Enabled')
           for d in config['UEFI']['Drivers']):
        take('OC/Resources')
    return n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true', help='show available profiles and exit')
    ap.add_argument('--catalogue', action='store_true',
                    help='list the published configs by name and exit')
    ap.add_argument('--name', help='build a published config by its catalogue name')
    ap.add_argument('--platform', choices=('desktop', 'laptop'))
    ap.add_argument('--vendor', choices=('intel', 'amd'))
    ap.add_argument('--cpu')
    ap.add_argument('--chipset')
    ap.add_argument('--oem')
    ap.add_argument('--variant')
    ap.add_argument('--cores', type=int)
    ap.add_argument('--oc', help='OpenCore version to build against (default: newest vendored)')
    ap.add_argument('--out', default='build/EFI')
    ap.add_argument('--identity', choices=('generate', 'placeholder'), default='generate')
    ap.add_argument('--no-validate', action='store_true')
    ap.add_argument('--add-kexts', help='JSON file of extra Kernel.Add entries to append')
    ap.add_argument('--boot-args', help='extra boot arguments to append to the config')
    ap.add_argument('--notes', help='file of follow-up notes to write beside the EFI')
    ap.add_argument('--device-props', help='JSON of DeviceProperties to merge in')
    ap.add_argument('--acpi', metavar='DIR',
                    help='a SSDTTime Results folder: its SSDTs and patches go in')
    ap.add_argument('--drop-kexts', help='bundle names to disable, comma separated')
    a = ap.parse_args(argv)

    cat = {e['name']: e for e in
           ocgen.read_toml(PROFILES / 'catalogue.toml')['config']} \
        if (PROFILES / 'catalogue.toml').exists() else {}

    if a.catalogue:
        for name in cat:
            print(f'  {name}')
        print(f'\n  {len(cat)} published configs; build one with --name "<name>"')
        return 0

    if a.list:
        for plat, cpus in available().items():
            print(f'  {plat}')
            for c in cpus:
                print(f'      {c}')
        for kind in ('chipset', 'oem', 'variant'):
            names = sorted(p.stem.split('.', 1)[1]
                           for p in PROFILES.glob(f'overlay/{kind}.*.toml'))
            if names:
                print(f'  --{kind}: {", ".join(names)}')
        return 0
    if a.name:
        e = cat.get(a.name)
        if not e:
            near = [n for n in cat if a.name.lower() in n.lower()][:8]
            sys.exit(f'no catalogue entry named {a.name!r}'
                     + (f'; did you mean:\n  ' + '\n  '.join(near) if near else
                        '; use --catalogue to list them'))
        for k in ('platform', 'vendor', 'cpu', 'chipset', 'oem', 'variant', 'cores'):
            setattr(a, k, e.get(k))
    if not (a.platform and a.cpu):
        ap.error('--platform and --cpu are required (or --name, or --list)')
    if a.platform == 'desktop' and not a.vendor:
        ap.error('--vendor is required for desktop (intel or amd)')

    warnings = []
    warn = warnings.append

    sample_path = ocgen.vendored_sample(a.oc)
    if not sample_path:
        sys.exit(f'no vendored OpenCore {a.oc or ""}; have: '
                 f'{", ".join(ocgen.vendored_versions()) or "none"}')
    version = Path(sample_path).parent.name

    row = row_from_args(a)
    if a.name:
        row['path'] = f'{ocgen.CONFIG_ROOT}/{a.name}.plist'   # picks up its residual
    key = f"{row['platform']}-{row['vendor'] or ''}/{row['cpu']}"
    lo, hi, tested = ocgen.support_range(PROFILES, key)
    why = ocgen.version_supported(version, lo, hi)
    if why:
        warn(f'OpenCore {version} is {why} for this profile'
             + (f' (tested: {", ".join(tested)})' if tested else ''))
    chain = ocgen.layer_chain(row, PROFILES)
    config = ocgen.assemble(ocgen.load_plist(sample_path), chain, ocgen.build_params(row))

    for axis in ('chipset', 'oem', 'variant'):
        if row[axis] and not (PROFILES / 'overlay' / f'{axis}.{row[axis]}.toml').exists():
            warn(f'no {axis} profile named {row[axis]!r}; it was ignored')

    added = []
    if a.add_kexts:
        import json
        with open(a.add_kexts) as fh:
            added = json.load(fh)
        have = {k['BundlePath'] for k in config['Kernel']['Add']}
        # appended, not merged in: everything already there was ordered by a
        # profile, and Lilu - which IntelBTPatcher needs - is always first
        config['Kernel']['Add'] += [{k: v for k, v in e.items() if k != 'SourcePath'}
                                    for e in added if e['BundlePath'] not in have]

    guid = '7C436110-AB2A-4BBB-A880-FE41995C9F82'
    if a.boot_args:
        nv = config['NVRAM']['Add'][guid]
        have = nv.get('boot-args', '').split()
        for arg in a.boot_args.split():
            key = arg.split('=')[0] + '=' if '=' in arg else None
            if key:
                # a key=value argument replaces one already set, since most
                # profiles ship alcid=1 and appending a second would be ignored
                have = [x for x in have if not x.startswith(key)]
            if arg not in have:
                have.append(arg)
        nv['boot-args'] = ' '.join(have)

    if a.device_props:
        import json
        with open(a.device_props) as fh:
            props = json.load(fh)
        add = config['DeviceProperties']['Add']
        for path, values in props.items():
            target = add.setdefault(path, {})
            for k, v in values.items():
                old = target.get(k)
                if v is None:
                    # null means remove: leaving a placeholder in place is not the
                    # same as choosing not to set the key, and only one of those
                    # is what somebody asked for
                    if k in target:
                        del target[k]
                        warn(f'{path} {k}: removed '
                             f'{bytes(old).hex() if isinstance(old, bytes) else old}')
                    continue
                target[k] = bytes.fromhex(v[4:]) if isinstance(v, str) and v.startswith('hex:') else v
                if old is not None and old != target[k]:
                    warn(f'{path} {k}: replaced {bytes(old).hex() if isinstance(old, bytes) else old}')

    acpi_extra = []
    if a.acpi:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import acpi as acpi_tool
        acpi_extra, add, patches = acpi_tool.collect(a.acpi)
        for entry in add:
            # the profiles ship generic SSDTs - SSDT-PLUG-DRTNIA, SSDT-EC-USBX-
            # LAPTOP - and SSDTTime writes ones built against this machine's own
            # tables. Two SSDTs doing the same job is not additive, so the one
            # made for the machine wins and the generic one is turned off, out
            # loud, because that is a decision and not a merge.
            for old_entry in config['ACPI']['Add']:
                if old_entry['Path'] == entry['Path']:
                    # the same name is a replacement, not a conflict: the file in
                    # the EFI is overwritten and the entry is rewritten below
                    warn(f'{entry["Path"]} replaced by the one built for this '
                         f'machine')
                elif acpi_tool.same_purpose(old_entry['Path'], entry['Path']):
                    if old_entry.get('Enabled'):
                        warn(f'{old_entry["Path"]} disabled: {entry["Path"]} is '
                             f'built for this machine and does the same job')
                    old_entry['Enabled'] = False
            config['ACPI']['Add'] = [e for e in config['ACPI']['Add']
                                     if e['Path'] != entry['Path']]
            config['ACPI']['Add'].append(entry)
        # the patches are the tool's own, written as OpenCore wants them, so
        # they go in as they are rather than being rebuilt from a reading of it
        seen = {(bytes(e.get('Find') or b''), bytes(e.get('Replace') or b''))
                for e in config['ACPI']['Patch']}
        fresh = [p_ for p_ in patches
                 if (bytes(p_.get('Find') or b''),
                     bytes(p_.get('Replace') or b'')) not in seen]
        if len(fresh) != len(patches):
            warn(f'{len(patches) - len(fresh)} ACPI patches were already in the '
                 f'config and were not added twice')
        config['ACPI']['Patch'].extend(fresh)
        if add or fresh:
            print(f'  ACPI         {len(add)} SSDTs, {len(fresh)} patches from '
                  f'{a.acpi}')

    if a.drop_kexts:
        drop = {x.strip() for x in a.drop_kexts.split(',') if x.strip()}
        before = len(config['Kernel']['Add'])
        config['Kernel']['Add'] = [k for k in config['Kernel']['Add']
                                   if k['BundlePath'] not in drop]
        if before != len(config['Kernel']['Add']):
            print(f'  dropped      {", ".join(sorted(drop))}')

    serial = apply_identity(config, a.identity, warn)

    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    copied = copy_payload(config, out, warn,
                          {e['BundlePath']: e['SourcePath']
                           for e in added if e.get('SourcePath')},
                          extra_acpi=acpi_extra)
    cfg = out / 'OC' / 'config.plist'
    cfg.parent.mkdir(parents=True, exist_ok=True)
    with open(cfg, 'wb') as fh:
        plistlib.dump(config, fh, sort_keys=False)

    status = 'skipped'
    if not a.no_validate:
        tool = ocgen.vendored_tool('ocvalidate', version)
        if not tool:
            warn('ocvalidate not available for this platform; config was not validated')
        else:
            r = subprocess.run([str(tool), str(cfg)], capture_output=True, text=True)
            status = 'clean' if 'No issues found' in r.stdout else 'ISSUES'
            if status == 'ISSUES':
                print(r.stdout)

    print(f'  OpenCore     {version}' + (f'   tested {lo}-{tested[-1] if tested else "?"}' if lo else ''))
    print(f'  profiles     ' + ' -> '.join(p.stem for p in chain))
    print(f'  SMBIOS       {config["PlatformInfo"]["Generic"]["SystemProductName"]}'
          + (f'  {serial}' if serial else ''))
    if added:
        print(f'  added kexts  ' + ', '.join(e['BundlePath'] for e in added))
    if a.boot_args:
        print(f'  boot-args    {config["NVRAM"]["Add"][guid]["boot-args"]}')
    print(f'  payload      {copied} items')
    print(f'  ocvalidate   {status}')
    if a.notes and Path(a.notes).exists():
        target = out.parent / 'NEXT-STEPS.txt'
        target.write_text(Path(a.notes).read_text(encoding='utf-8'), encoding='utf-8')
        print(f'  notes        {target}')
    print(f'  output       {out}')
    for w in warnings:
        print(f'  warning      {w}')
    return 1 if status == 'ISSUES' else 0


if __name__ == '__main__':
    sys.exit(main())
