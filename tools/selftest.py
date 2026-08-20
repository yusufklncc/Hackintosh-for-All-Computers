"""Assertions about the advice the tools give.

These live here rather than inline in the workflow because YAML plus a shell
plus embedded Python is three levels of quoting, and getting one wrong breaks
the whole file before a single step runs - which is exactly what happened.

    python3 tools/selftest.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audio
import detect
import gpu
import ocgen

FAILED = []


def run(cmd):
    """Run a tool and, if it fails, say what it said.

    capture_output with check=True raises a CalledProcessError carrying only the
    command line, so a failure here used to reach CI as 'exit status 1' with the
    reason discarded - which is worse than no test."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f'\n  --- {" ".join(cmd)} exited {r.returncode} ---')
        for stream in (r.stdout, r.stderr):
            for line in (stream or '').strip().splitlines():
                print(f'  | {line}')
        print('  ---')
    return r


def check(name, condition, detail=''):
    print(f'  {"ok  " if condition else "FAIL"}  {name}' + (f'   {detail}' if not condition else ''))
    if not condition:
        FAILED.append(name)


def graphics():
    real, virt = detect.split_graphics([
        r'PCI\VEN_8086&DEV_E20B&SUBSYS_1&REV_08\6&a&0|Intel(R) Arc(TM) B580 Graphics',
        r'ROOT\DISPLAY\0000|Virtual Display Driver'])
    check('a virtual display driver is not the graphics card',
          [g['name'] for g in real] == ['Intel(R) Arc(TM) B580 Graphics'], real)
    check('the real card carries its pci id', real and real[0]['id'] == '8086:e20b', real)
    check('the virtual one is named, not dropped',
          [g['name'] for g in virt] == ['Virtual Display Driver'], virt)


def graphics_advice():
    arc = {'name': 'Intel Arc B580', 'id': '8086:e20b'}
    igpu_ok = {'name': 'Intel HD Graphics 630', 'id': '8086:5912'}
    igpu_no = {'name': 'Intel UHD Graphics 770', 'id': '8086:4680'}

    out = ' '.join(gpu.report([arc, igpu_ok], 'kaby-lake')[0])
    check('a supported igpu is offered as the fallback', 'you can disable it and use' in out)

    out = ' '.join(gpu.report([arc, igpu_no], 'alder-lake')[0])
    check('an unsupported igpu is not offered',
          'not supported either' in out and 'you can disable' not in out)

    out = ' '.join(gpu.report([arc], None)[0])
    check('with no igpu, no fallback is implied', 'no integrated GPU here' in out)

    out = ' '.join(gpu.report([arc, {'name': 'Intel HD Graphics 630', 'id': '8086:5912'}], None)[0])
    check('an unknown igpu is reported as unknown, not as absent',
          'could not be determined' in out, out)

    check('a supported card brings its boot argument',
          gpu.report([{'name': 'RX 6600', 'id': '1002:73ff'}], None)[1] == ['agdpmod=pikera'])


def audio_advice():
    lines, alcid, steps = audio.report(['10ec:0255'], 'lenovo')
    check('the brand a contributor named decides where to start', alcid == 28, alcid)
    check('the notes name that machine', 'Lenovo' in steps)
    check('without a brand it is the lowest id', audio.report(['10ec:0255'], None)[1] == 3)
    check('every layout reaches the notes, not just the three shown',
          steps.count('alcid=') >= 27, steps.count('alcid='))
    check('an unknown codec picks nothing', audio.report(['8086:2809'], None)[1] is None)


def boot_args():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'EFI'
        r = run([sys.executable, 'tools/setup.py', '--hda-ids', '10ec:0255',
                 '--answers', '1,2,10,3', '--out', str(out)])
        check('the guided build succeeds', r.returncode == 0)
        if r.returncode != 0:
            return
        cfg = ocgen.load_plist(out / 'OC' / 'config.plist')
        args = cfg['NVRAM']['Add']['7C436110-AB2A-4BBB-A880-FE41995C9F82']['boot-args']
        check('alcid replaces the one the profile ships',
              'alcid=3' in args and args.count('alcid=') == 1, args)
        check('the follow-up notes are written beside the EFI',
              (out.parent / 'NEXT-STEPS.txt').exists())


def storage():
    import netkexts
    third, _ = netkexts.storage_entries(['Samsung SSD 970 EVO Plus'])
    check('a third-party NVMe gets NVMeFix',
          [e['BundlePath'] for e in third] == ['NVMeFix.kext'], third)
    check('an Apple NVMe does not, being the case it is not for',
          netkexts.storage_entries(['APPLE SSD AP0512'])[0] == [])
    check('a machine with no NVMe does not', netkexts.storage_entries([])[0] == [])
    check('NVMeFix is bounded to the version its README requires',
          third and third[0]['MinKernel'] == '18.0.0', third)


def peripherals():
    found = detect.peripherals(
        'Camera|USB\\VID_04F2&PID_B67C&MI_00\\6&a|Integrated Camera\n'
        'Image|PCI\\VEN_8086&DEV_9D32\\3&b|Intel Imaging Signal Processor\n'
        'SDHost|PCI\\VEN_10EC&DEV_5229\\4&c|Realtek PCIE CardReader')
    kinds = [(d['kind'], d['usb']) for d in found]
    check('a usb camera is told apart from an on-board sensor',
          ('camera', True) in kinds and ('camera', False) in kinds, kinds)
    check('a card reader is recognised as one', ('card reader', False) in kinds, kinds)


def trackpad():
    import inputdev
    lines, kexts = inputdev.entries(['8086:9d60'], False)
    check('an I2C controller brings VoodooI2C and its HID plugin',
          [k['BundlePath'] for k in kexts] == ['VoodooI2C.kext', 'VoodooI2CHID.kext'], kexts)
    check('the keyboard warning is repeated, since PS2 is separate',
          any('Most laptop keyboards are PS2' in l for l in lines))
    check('a machine with no I2C controller gets nothing',
          inputdev.entries(['8086:15b8'], False)[1] == [])
    check('a PS/2 device present is called out as making it doubtful',
          any('may well be PS/2' in l for l in inputdev.entries(['8086:9d60'], True)[0]))


def framebuffer():
    import igpu
    lines, props, steps = igpu.report('ivy-bridge', True, True)
    ids = [c['value'] for c in igpu.candidates('ivy-bridge', True)]
    check('the recommended id comes before the alternatives',
          ids and ids[0] == '0x01660004', ids)
    check('it is written byte-swapped, as DeviceProperties wants',
          props[igpu.IGPU_PATH]['AAPL,ig-platform-id'] == 'hex:04006601', props)
    listed = [l for l in steps.splitlines() if l.strip().startswith('0x')]
    check('every candidate reaches the notes', len(listed) == len(ids),
          f'{len(listed)} listed, {len(ids)} candidates')
    check('headless is never the one to start with',
          igpu.candidates('kaby-lake', False)[0]['value'] == '0x59160000')
    check('an unsupported generation is offered nothing',
          igpu.report('alder-lake', False, False)[1] == {})


def other_machine():
    """A report has to survive the trip and be refused when it is not one."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'machine.json'
        written = detect.write_report(path)
        back, complaint = detect.read_report(path)
        check('a report reads back as it was written', complaint is None, complaint)
        if back:
            check('the ids survive the round trip',
                  back['pci_ids'] == written['pci_ids']
                  and back['usb_ids'] == written['usb_ids']
                  and back['hda_ids'] == written['hda_ids'])
            check('it says which machine and when it was taken',
                  bool(back.get('written')) and 'system' in back)
        check('the raw device dump is not carried into a file meant to be sent',
              'pci' not in json.loads(path.read_text()))

        junk = Path(tmp) / 'junk.json'
        junk.write_text('{"cpu": "something"}')
        check('a file that is not a report is refused, not half-read',
              detect.read_report(junk)[0] is None)
        check('a missing file is refused', detect.read_report(Path(tmp) / 'no.json')[0] is None)

        ahead = json.loads(path.read_text())
        ahead['report_version'] = detect.REPORT_VERSION + 1
        newer = Path(tmp) / 'newer.json'
        newer.write_text(json.dumps(ahead))
        check('a report from a newer tool is refused rather than guessed at',
              detect.read_report(newer)[0] is None)

        # named by hand, because nothing about that machine can be detected
        out = Path(tmp) / 'EFI'
        r = run([sys.executable, 'tools/setup.py', '--answers', '3,2,10,3,1,2,1,1',
                 '--out', str(out)])
        check('naming the hardware of another machine builds', r.returncode == 0)
        if r.returncode == 0:
            have = {p.name for p in (out / 'OC' / 'Kexts').iterdir()}
            check('what was named is added', 'IntelMausi.kext' in have
                  and 'IntelBluetoothFirmware.kext' in have, sorted(have))
            check('what was declined is not', 'AirportItlwm.kext' not in have)
            check('nothing is claimed about graphics it cannot see',
                  not (out.parent / 'NEXT-STEPS.txt').exists())


def tables_match_sources():
    with tempfile.TemporaryDirectory() as tmp:
        gen = Path(tmp) / 'hardware.toml'
        r = run([sys.executable, 'tools/hwtable.py', 'EFI/OC/Kexts', '--out', str(gen)])
        if r.returncode != 0:
            check('the hardware table regenerates', False)
            return
        check('the hardware table still matches the kexts',
              gen.read_text() == Path('data/hardware.toml').read_text())


if __name__ == '__main__':
    for section in (graphics, graphics_advice, audio_advice, storage, peripherals,
                    trackpad, framebuffer, boot_args, other_machine,
                    tables_match_sources):
        print(f'\n{section.__name__}')
        section()
    print()
    if FAILED:
        sys.exit(f'{len(FAILED)} failed: {", ".join(FAILED)}')
    print('  all good')
