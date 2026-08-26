"""Make the icon files each system wants, from one master.

Three systems, three containers, one drawing. The master is
`gui/Assets/Icon/icon-1024.png`; everything else here is derived from it and
committed, because the tools that do the deriving are macOS-only and the
Windows and Linux builds run elsewhere.

    python3 tools/icons.py --check    # the derivatives are here and the right shape
    python3 tools/icons.py --build    # regenerate them (macOS: sips, iconutil)

The master is not the drawing as it arrived. macOS applies no mask - an icon is
exactly the pixels it is given - and Apple's own icons leave a margin so that
every icon in a Dock lines up. Measured on this machine: Calculator, Notes and
Maps all put an 880x880 shape in a 1024x1024 frame. A drawing that fills 75% of
its frame looks a size smaller than everything beside it, so the master is
cropped to its shape and padded back to that proportion.
"""
import argparse
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ICONS = Path('gui/Assets/Icon')
MASTER = ICONS / 'icon-1024.png'
ICNS = ICONS / 'HackintoshEFIBuilder.icns'
ICO = ICONS / 'HackintoshEFIBuilder.ico'
PNGS = ICONS / 'png'

# What Apple's own icons do, measured rather than remembered
FRAME = 1024
SHAPE = 880
# the sizes each container carries
MAC = (16, 32, 128, 256, 512)
WINDOWS = (16, 32, 48, 256)
LINUX = (16, 32, 48, 64, 128, 256, 512)


def read_png(path):
    """(width, height, rows of RGBA bytes) for an 8-bit RGBA PNG.

    Written out rather than reached for: this repository has no image library
    and one icon is not a reason to acquire one."""
    data = Path(path).read_bytes()
    pos, idat, w, h = 8, b'', 0, 0
    depth = colour = 0
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b'IHDR':
            w, h, depth, colour = struct.unpack('>IIBB', body[:10])
        elif kind == b'IDAT':
            idat += body
    if (depth, colour) != (8, 6):
        raise SystemExit(f'{path}: not 8-bit RGBA (depth {depth}, colour {colour})')
    raw = zlib.decompress(idat)
    stride, prev, rows, at = w * 4, bytearray(w * 4), [], 0
    for _ in range(h):
        filt = raw[at]; at += 1
        line = bytearray(raw[at:at + stride]); at += stride
        for x in range(stride):
            left = line[x - 4] if x >= 4 else 0
            up = prev[x]
            upleft = prev[x - 4] if x >= 4 else 0
            if filt == 1:
                line[x] = (line[x] + left) & 255
            elif filt == 2:
                line[x] = (line[x] + up) & 255
            elif filt == 3:
                line[x] = (line[x] + (left + up) // 2) & 255
            elif filt == 4:
                guess = left + up - upleft
                pa, pb, pc = abs(guess - left), abs(guess - up), abs(guess - upleft)
                near = left if (pa <= pb and pa <= pc) else (up if pb <= pc else upleft)
                line[x] = (line[x] + near) & 255
        rows.append(bytes(line)); prev = line
    return w, h, rows


def shape_of(path, threshold=40):
    """The box the drawing actually occupies, ignoring a faint outer glow."""
    w, h, rows = read_png(path)
    solid = [[r[x * 4 + 3] > threshold for x in range(w)] for r in rows]
    top = next(y for y, r in enumerate(solid) if any(r))
    bottom = next(y for y in range(h - 1, -1, -1) if any(solid[y]))
    left = min(next((x for x, on in enumerate(r) if on), w) for r in solid)
    right = max(max((x for x, on in enumerate(r) if on), default=-1) for r in solid)
    return w, h, left, right, top, bottom


def _sips(*args):
    done = subprocess.run(['sips', *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(f'sips {" ".join(args)}: {done.stderr.strip()[:200]}')


def build():
    """Regenerate every derivative. macOS only: sips and iconutil live there."""
    if sys.platform != 'darwin':
        raise SystemExit('building these needs sips and iconutil, so macOS. '
                         'The results are committed for that reason.')
    if not MASTER.exists():
        raise SystemExit(f'{MASTER} is not here')

    PNGS.mkdir(parents=True, exist_ok=True)
    for size in sorted(set(LINUX) | set(WINDOWS) | set(MAC)):
        _sips('-Z', str(size), str(MASTER), '--out', str(PNGS / f'icon-{size}.png'))

    # .icns, through the layout iconutil insists on
    work = Path(os.environ.get('TMPDIR', '/tmp')) / 'icon.iconset'
    subprocess.run(['rm', '-rf', str(work)], check=False)
    work.mkdir(parents=True)
    for size in MAC:
        _sips('-Z', str(size), str(MASTER),
              '--out', str(work / f'icon_{size}x{size}.png'))
        _sips('-Z', str(size * 2), str(MASTER),
              '--out', str(work / f'icon_{size}x{size}@2x.png'))
    done = subprocess.run(['iconutil', '-c', 'icns', str(work), '-o', str(ICNS)],
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(f'iconutil: {done.stderr.strip()[:200]}')

    write_ico()
    return sorted(p.name for p in ICONS.rglob('*') if p.is_file())


def write_ico():
    """An .ico holding PNGs, which Windows has read since Vista.

    The older format stores a bitmap per size with its own mask, and writing
    that by hand for four sizes is a lot of code to draw the same picture."""
    entries = []
    for size in WINDOWS:
        blob = (PNGS / f'icon-{size}.png').read_bytes()
        entries.append((size, blob))
    header = struct.pack('<HHH', 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    directory, images = b'', b''
    for size, blob in entries:
        # 0 means 256 in this field, which is the whole reason it is a byte
        directory += struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0,
                                 1, 32, len(blob), offset)
        offset += len(blob)
        images += blob
    ICO.write_bytes(header + directory + images)


def check():
    """Everything is here, and the master is the shape macOS expects."""
    trouble = []
    if not MASTER.exists():
        return [f'{MASTER} is missing']
    w, h, left, right, top, bottom = shape_of(MASTER)
    if (w, h) != (FRAME, FRAME):
        trouble.append(f'the master is {w}x{h}, not {FRAME}x{FRAME}')
    wide, tall = right - left + 1, bottom - top + 1
    if abs(wide - SHAPE) > 8 or abs(tall - SHAPE) > 8:
        trouble.append(f'the drawing is {wide}x{tall} in a {w} frame; macOS icons '
                       f'put {SHAPE}x{SHAPE} there, so this would look a size '
                       f'smaller than everything beside it')
    for path in (ICNS, ICO):
        if not path.exists():
            trouble.append(f'{path} is missing; run --build on macOS')
    for size in LINUX:
        png = PNGS / f'icon-{size}.png'
        if not png.exists():
            trouble.append(f'{png} is missing')
            continue
        got = read_png(png)[:2]
        if got != (size, size):
            trouble.append(f'{png} is {got[0]}x{got[1]}, not {size}x{size}')
    return trouble


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--build', action='store_true', help='regenerate (macOS only)')
    ap.add_argument('--check', action='store_true', help='say what is missing or wrong')
    a = ap.parse_args(argv)

    if a.build:
        for name in build():
            print(f'  {name}')
        return 0

    trouble = check()
    for said in trouble:
        print(f'  {said}')
    if not trouble:
        w, h, left, right, top, bottom = shape_of(MASTER)
        print(f'  master {w}x{h}, drawing {right - left + 1}x{bottom - top + 1}, '
              f'margins {left}')
        print(f'  {ICNS.name}, {ICO.name}, and {len(LINUX)} PNGs')
    return 1 if trouble else 0


if __name__ == '__main__':
    raise SystemExit(main())
