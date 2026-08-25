"""Find the USB stick, and put the EFI and the installer on it.

Everything else here writes into a folder and stops. This is the only part that
touches a whole disk, so it is the only part that can destroy something, and it
is written to make that hard rather than convenient:

  * only removable, external, physical disks are ever listed. An internal drive
    is not "hidden" behind a warning, it is not in the list at all,
  * the disk this computer booted from is removed from that list by its own
    identifier, not by being assumed to be first,
  * the list is what naming works against: a device nobody was offered cannot
    be erased by typing it in,
  * and the check is made again at the moment of erasing, because somebody can
    unplug one stick and plug in another between reading and pressing.

Copying needs none of that and is the part most people want, so it is separate:
a stick that is already FAT32 needs no erasing at all.

    python3 tools/usb.py --list
    python3 tools/usb.py --place /Volumes/USB --efi build/EFI --recovery .
    python3 tools/usb.py --prepare disk4        # erases it, and says so twice
"""
import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui

BOLD, DIM, GREEN, YELLOW, RED, RESET = ui.colours(
    'bold', 'dim', 'green', 'yellow', 'red', 'reset')

RECOVERY = 'com.apple.recovery.boot'
# What OpenCore boots. A stick without this is not a boot disk, whatever else
# is on it, so the copy checks for it rather than trusting a folder name.
LOADER = Path('EFI') / 'BOOT' / 'BOOTx64.efi'


def _run(*command):
    """A command and its output, or None when it is not there to run."""
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return done


def _sizeof(count):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if count < 1024 or unit == 'TB':
            return f'{count:.0f} {unit}' if unit == 'B' else f'{count:.1f} {unit}'
        count /= 1024
    return ''


# --- what this computer booted from ------------------------------------------

def _booted_from():
    """The whole disk holding the running system, so it can be left out.

    Named, not guessed. "the first disk" and "the internal one" are both wrong
    on some machine somebody owns."""
    if sys.platform == 'darwin':
        got = _run('diskutil', 'info', '-plist', '/')
        if got and got.returncode == 0:
            try:
                return plistlib.loads(got.stdout.encode()).get('ParentWholeDisk')
            except Exception:                      # noqa: BLE001 - shape unknown
                return None
    if sys.platform.startswith('linux'):
        got = _run('findmnt', '-no', 'SOURCE', '/')
        if got and got.returncode == 0:
            part = got.stdout.strip()
            whole = _run('lsblk', '-no', 'PKNAME', part)
            if whole and whole.returncode == 0 and whole.stdout.strip():
                return whole.stdout.strip().splitlines()[0]
    if sys.platform.startswith('win'):
        got = _run('powershell', '-NoProfile', '-Command',
                   '(Get-Partition -DriveLetter '
                   '$env:SystemDrive.Substring(0,1)).DiskNumber')
        if got and got.returncode == 0 and got.stdout.strip().isdigit():
            return got.stdout.strip()
    return None


# --- the sticks ---------------------------------------------------------------

def _macos_sticks():
    """Whole disks diskutil calls external and physical, and nothing else."""
    got = _run('diskutil', 'list', '-plist', 'external', 'physical')
    if not got or got.returncode != 0:
        return []
    try:
        listed = plistlib.loads(got.stdout.encode()).get('WholeDisks', [])
    except Exception:                              # noqa: BLE001 - shape unknown
        return []
    out = []
    for device in listed:
        info = _run('diskutil', 'info', '-plist', f'/dev/{device}')
        if not info or info.returncode != 0:
            continue
        try:
            about = plistlib.loads(info.stdout.encode())
        except Exception:                          # noqa: BLE001
            continue
        # external and physical is diskutil's answer; these two are ours, and
        # they are what stops a Thunderbolt drive somebody works off
        if about.get('Internal'):
            continue
        out.append({
            'device': device,
            'name': (about.get('MediaName') or '').strip() or 'unnamed',
            'bytes': int(about.get('TotalSize') or 0),
            'bus': about.get('BusProtocol') or '',
            'removable': bool(about.get('Removable')
                              or about.get('RemovableMediaOrExternalDevice')
                              or about.get('Ejectable')),
            'mounted': _macos_mounts(device),
        })
    return out


def _macos_mounts(device):
    got = _run('diskutil', 'list', '-plist', f'/dev/{device}')
    if not got or got.returncode != 0:
        return []
    try:
        listed = plistlib.loads(got.stdout.encode())
    except Exception:                              # noqa: BLE001
        return []
    where = []
    for disk in listed.get('AllDisksAndPartitions', []):
        for part in disk.get('Partitions', []) or []:
            if part.get('MountPoint'):
                where.append(part['MountPoint'])
    return where


def _linux_sticks():
    got = _run('lsblk', '-J', '-b', '-o',
               'NAME,SIZE,RM,TRAN,MODEL,TYPE,MOUNTPOINT')
    if not got or got.returncode != 0:
        return []
    try:
        tree = json.loads(got.stdout)
    except json.JSONDecodeError:
        return []
    out = []
    for disk in tree.get('blockdevices', []):
        if disk.get('type') != 'disk':
            continue
        removable = bool(disk.get('rm')) or disk.get('tran') == 'usb'
        if not removable:
            continue
        mounted = [p['mountpoint'] for p in disk.get('children', []) or []
                   if p.get('mountpoint')]
        if disk.get('mountpoint'):
            mounted.append(disk['mountpoint'])
        out.append({
            'device': disk['name'],
            'name': (disk.get('model') or '').strip() or 'unnamed',
            'bytes': int(disk.get('size') or 0),
            'bus': disk.get('tran') or '',
            'removable': removable,
            'mounted': mounted,
        })
    return out


def _windows_sticks():
    script = ("Get-Disk | Where-Object BusType -eq 'USB' | "
              "ForEach-Object { $d = $_; "
              "$m = (Get-Partition -DiskNumber $d.Number -ErrorAction SilentlyContinue "
              "| Where-Object DriveLetter | ForEach-Object { \"$($_.DriveLetter):\\\" }) "
              "-join ','; "
              "[pscustomobject]@{ device = \"$($d.Number)\"; "
              "name = $d.FriendlyName; bytes = $d.Size; bus = 'USB'; "
              "mounted = $m } } | ConvertTo-Json -AsArray")
    got = _run('powershell', '-NoProfile', '-Command', script)
    if not got or got.returncode != 0:
        return []
    try:
        listed = json.loads(got.stdout or '[]')
    except json.JSONDecodeError:
        return []
    out = []
    for disk in listed:
        out.append({
            'device': str(disk.get('device')),
            'name': (disk.get('name') or '').strip() or 'unnamed',
            'bytes': int(disk.get('bytes') or 0),
            'bus': 'USB',
            'removable': True,
            'mounted': [m for m in (disk.get('mounted') or '').split(',') if m],
        })
    return out


def sticks():
    """Every disk this may write to, with the boot disk taken out.

    An empty list means no removable disk was found, which on a laptop with
    nothing plugged in is the right answer and not a failure."""
    finder = {'darwin': _macos_sticks}.get(sys.platform)
    if finder is None:
        finder = _linux_sticks if sys.platform.startswith('linux') else (
            _windows_sticks if sys.platform.startswith('win') else None)
    if finder is None:
        return []
    booted = _booted_from()
    out = []
    for stick in finder():
        if booted and stick['device'] == booted:
            continue
        stick['size'] = _sizeof(stick['bytes'])
        out.append(stick)
    return sorted(out, key=lambda s: s['device'])


def offered(device):
    """The stick by that name, but only if it was in the list.

    Read again rather than remembered: between somebody being shown a list and
    pressing the button, a stick can be pulled out and another put in."""
    asked = (device or '').strip().removeprefix('/dev/')
    for stick in sticks():
        if stick['device'] == asked:
            return stick
    return None


# --- putting the folders on it -------------------------------------------------

def place(volume, efi=None, recovery=None):
    """Copy an EFI folder and a recovery folder to the root of a volume.

    Returns (written, complaint). Both are optional: a stick that already has
    one of them and needs the other is an ordinary thing."""
    root = Path(volume).expanduser()
    if not root.is_dir():
        return [], f'{root} is not a folder this can write to'
    written = []

    if efi:
        source = Path(efi).expanduser()
        if source.name.upper() != 'EFI' and (source / 'EFI').is_dir():
            source = source / 'EFI'          # somebody named the folder above it
        if not (source / 'BOOT' / 'BOOTx64.efi').exists():
            return [], (f'{source} has no BOOT/BOOTx64.efi in it, so it is not '
                        'an EFI folder OpenCore would boot')
        target = root / 'EFI'
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        written.append(('EFI', sum(f.stat().st_size for f in target.rglob('*')
                                   if f.is_file())))

    if recovery:
        source = Path(recovery).expanduser()
        if source.name != RECOVERY and (source / RECOVERY).is_dir():
            source = source / RECOVERY
        if not any(source.glob('BaseSystem.*')):
            return written, (f'{source} holds no BaseSystem, so there is no '
                             'installer here to copy')
        target = root / RECOVERY
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        written.append((RECOVERY, sum(f.stat().st_size for f in target.rglob('*')
                                      if f.is_file())))

    if not written:
        return [], 'nothing was named to copy'
    return written, None


def bootable(volume):
    """Whether what is on this volume would boot, said as a fact not a hope."""
    root = Path(volume).expanduser()
    return (root / LOADER).exists()


# --- erasing it ----------------------------------------------------------------

def prepare(device, label='USB'):
    """Erase a stick to one FAT32 partition under GPT. Returns (mount, complaint).

    This destroys what is on it. The device has to be one `sticks()` offered at
    the moment this runs; nothing else is accepted, and the caller having asked
    a minute ago is not enough."""
    stick = offered(device)
    if stick is None:
        return None, (f'{device} is not one of the removable disks this can '
                      'write to, so it will not be erased')

    if sys.platform == 'darwin':
        done = _run('diskutil', 'eraseDisk', 'MS-DOS', label, 'GPT',
                    f'/dev/{stick["device"]}')
        if done is None or done.returncode != 0:
            return None, _said(done)
        return _macos_mounts(stick['device'])[:1] or [None], None
    if sys.platform.startswith('linux'):
        return None, ('erasing a disk needs root on Linux, and this does not ask '
                      f'for it. Run: sudo sgdisk --zap-all /dev/{stick["device"]} '
                      f'&& sudo sgdisk -n 1:0:0 -t 1:0700 /dev/{stick["device"]} '
                      f'&& sudo mkfs.vfat -F 32 -n {label} /dev/{stick["device"]}1')
    if sys.platform.startswith('win'):
        return None, ('erasing a disk needs an administrator on Windows, and '
                      'this is not running as one. Open diskpart as '
                      f'administrator: select disk {stick["device"]}, clean, '
                      'convert gpt, create partition primary, '
                      f'format fs=fat32 quick label={label}, assign')
    return None, f'no way to erase a disk on {sys.platform}'


def _said(done):
    if done is None:
        return 'the tool that does this is not on this machine'
    for stream in (done.stderr, done.stdout):
        if (stream or '').strip():
            return (stream or '').strip().splitlines()[-1]
    return f'it exited {done.returncode}'


def document():
    """The list as a front end reads it, with what it is allowed to do.

    `erasable` is not a guess about permissions: it is what prepare() would do
    on this system, so a window can grey a button out instead of offering one
    that always fails."""
    return {
        't': 'sticks',
        'platform': sys.platform,
        'booted': _booted_from(),
        'erasable': sys.platform == 'darwin',
        'recovery': RECOVERY,
        'sticks': sticks(),
    }


# --- the console ---------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--list', action='store_true',
                    help='the removable disks this could write to')
    ap.add_argument('--place', metavar='VOLUME',
                    help='copy onto a stick that is already formatted')
    ap.add_argument('--efi', help='the EFI folder to copy')
    ap.add_argument('--recovery', help='the folder holding com.apple.recovery.boot')
    ap.add_argument('--prepare', metavar='DEVICE',
                    help='ERASE this disk and format it FAT32 under GPT')
    ap.add_argument('--yes', action='store_true',
                    help='answer the erase confirmation, for scripting')
    a = ap.parse_args(argv)

    if a.prepare:
        stick = offered(a.prepare)
        if stick is None:
            print(f'{YELLOW}{a.prepare} is not one of the removable disks this '
                  f'can write to{RESET}')
            print(f'{DIM}  --list says which are{RESET}')
            return 1
        print(f'{RED}{BOLD}This erases everything on it.{RESET}')
        print(f"  {stick['device']}  {stick['name']}  {stick['size']}"
              + (f"  mounted at {', '.join(stick['mounted'])}"
                 if stick['mounted'] else ''))
        if not a.yes:
            # the name, not "y". A stick is picked out by what it says on it,
            # and a habit of pressing y is exactly what this is guarding
            typed = input(f"  type {stick['device']} to go ahead: ").strip()
            if typed != stick['device']:
                print(f'{DIM}  nothing was erased{RESET}')
                return 1
        mount, complaint = prepare(stick['device'])
        if complaint:
            print(f'{YELLOW}  {complaint}{RESET}')
            return 1
        print(f'{GREEN}  erased and formatted{RESET}'
              + (f', mounted at {mount}' if mount else ''))
        return 0

    if a.place:
        written, complaint = place(a.place, a.efi, a.recovery)
        if complaint:
            print(f'{YELLOW}{complaint}{RESET}')
            return 1
        print(f'{BOLD}Written to {a.place}{RESET}')
        for name, size in written:
            print(f'  {name:28} {_sizeof(size)}')
        if bootable(a.place):
            print(f'{GREEN}  {LOADER} is there, so this stick boots{RESET}')
        else:
            print(f'{YELLOW}  no {LOADER} here yet - copy the EFI folder too, '
                  f'or this will not boot{RESET}')
        return 0

    found = sticks()
    print(f'{BOLD}Removable disks{RESET}')
    if not found:
        print(f'{DIM}  none. Plug one in, or the disk you mean is not removable '
              f'- this only ever lists removable, external, physical disks, and '
              f'never the one this computer booted from.{RESET}')
        return 0
    for stick in found:
        print(f"  {stick['device']:10} {stick['name'][:28]:30} {stick['size']:>10}"
              f"  {DIM}{stick['bus']}{RESET}")
        if stick['mounted']:
            print(f"{DIM}             mounted at {', '.join(stick['mounted'])}{RESET}")
    print(f'{DIM}\n  The disk this computer booted from is not in this list, and '
          f'cannot be.{RESET}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
