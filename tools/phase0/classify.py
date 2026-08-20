"""Phase 0 / step 1: classify every config into layer coordinates."""
import plistlib, glob, os, re, json, sys, collections

ROOT = 'EFI/OC/config'
OEM_DIRS = {'HP', 'ASUS', 'MSI', 'DELL', 'SONY', 'DELL - SONY'}
VARIANT_DIRS = {'BIOS (v3006+)'}

def slug(s):
    s = s.lower().replace('ve ', '').replace('_', '-')
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s

def classify(path):
    rel = os.path.relpath(path, ROOT)
    parts = rel.split(os.sep)
    fname = parts[-1][:-len('.plist')]
    dirs = parts[:-1]

    platform = dirs[0].lower()                     # desktop | laptop
    i = 1
    vendor = None
    if platform == 'desktop':
        vendor = dirs[1].lower()                   # intel | amd
        i = 2

    oem = chipset = variant = None
    for d in dirs[i:]:
        if d in OEM_DIRS:      oem = slug(d)
        elif d in VARIANT_DIRS: variant = slug(d)
        else:                   chipset = slug(d)

    # "012 - Desktop - Coffe Lake"  /  "003 - Desktop - Ryzen ve Threadripper 8 Core"
    m = re.match(r'^(\d+)\s*-\s*(Desktop|Laptop)\s*-\s*(.+)$', fname)
    assert m, fname
    idx, _, desc = m.group(1), m.group(2), m.group(3)
    cores = None
    mc = re.search(r'\s(\d+)\s+Core$', desc)
    if mc:
        cores = int(mc.group(1))
        desc = desc[:mc.start()]
    return dict(path=path, platform=platform, vendor=vendor, cpu=slug(desc),
                cpu_label=desc.strip(), chipset=chipset, oem=oem, variant=variant,
                cores=cores, index=int(idx))

def main():
    rows = [classify(p) for p in sorted(glob.glob(f'{ROOT}/**/*.plist', recursive=True))]
    json.dump(rows, open(sys.argv[1], 'w'), indent=1)
    print(f'classified {len(rows)} configs\n')
    for key in ('platform', 'vendor', 'oem', 'chipset', 'variant'):
        c = collections.Counter(r[key] for r in rows)
        print(f'  {key:9s} {dict(c)}')
    print(f'\n  distinct cpu profiles: {len(set(r["cpu"] for r in rows))}')
    for cpu, n in sorted(collections.Counter(r["cpu"] for r in rows).items()):
        print(f'      {n:3d}x {cpu}')

if __name__ == '__main__':
    main()
