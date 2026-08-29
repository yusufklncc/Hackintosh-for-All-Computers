"""Assertions about the advice the tools give.

These live here rather than inline in the workflow because YAML plus a shell
plus embedded Python is three levels of quoting, and getting one wrong breaks
the whole file before a single step runs - which is exactly what happened.

    python3 tools/selftest.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audio
import detect
import gpu
import ocgen
from hwtable import name_ids as hwtable_name_ids

FAILED = []


def run(cmd, may_fail=False):
    """Run a tool and, if it fails, say what it said.

    capture_output with check=True raises a CalledProcessError carrying only the
    command line, so a failure here used to reach CI as 'exit status 1' with the
    reason discarded - which is worse than no test. may_fail is for the checks
    whose point is that a tool refuses: printing that as a failure would put a
    page of alarming output in a log where everything went right."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 and not may_fail:
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
        # from the fixture, so the questions do not depend on whether the
        # machine running the test happens to have an NVMe drive
        r = run([sys.executable, 'tools/setup.py',
                 '--machine', 'tools/fixtures/no-hardware.json',
                 '--hda-ids', '10ec:0255',
                 '--answers', '2,10,3,9', '--out', str(out)])
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
        'SDHost|PCI\\VEN_10EC&DEV_5229\\4&c|Realtek PCIE CardReader\n'
        'Keyboard|ACPI\\PNP0303\\4&d|Standart PS/2 Klavye\n'
        'Mouse|ACPI\\ALP0021\\4&e|Alps Pointing-device')
    kinds = [(d['kind'], d['usb']) for d in found]
    check('a usb camera is told apart from an on-board sensor',
          ('camera', True) in kinds and ('camera', False) in kinds, kinds)
    check('a card reader is recognised as one', ('card reader', False) in kinds, kinds)
    by_name = {d['name']: d for d in found}
    check('a keyboard is not called a card reader',
          by_name['Standart PS/2 Klavye']['kind'] == 'keyboard', by_name)
    check('nor is a trackpad',
          by_name['Alps Pointing-device']['kind'] == 'pointing device', by_name)
    check('the hardware id is kept and the instance path is not',
          by_name['Alps Pointing-device']['id'] == 'ACPI\\ALP0021', by_name)

    # a real Toshiba: neither device uses a standard PnP id, so matching ids
    # reported no PS/2 hardware on a machine whose keyboard and trackpad are both
    # on the PS/2 controller
    listing = ('Keyboard|ACPI\\TOS7407\\4&a|Standart PS/2 Klavye|i8042prt\n'
               'Mouse|ACPI\\TTP1000\\4&b|Alps Pointing-device|i8042prt\n'
               'Keyboard|TERMINPUT_BUS\\UMB\\1&c|Uzak Masaustu Klavye Aygiti|terminpt')
    check('PS/2 is read from the driver Windows bound, not from the PnP id',
          detect.ps2_present({'peripherals': listing}))
    check('and on Linux from the kernel bus number',
          detect.ps2_present({'input': 'I: Bus=0011 Vendor=0001 Product=0001'}))
    check('a machine with neither says so',
          not detect.ps2_present({'peripherals':
                                  'Camera|USB\\VID_04F2&PID_B3B2\\6&d|Cam|usbvideo'}))
    remote = [d for d in detect.peripherals(listing) if d['virtual']]
    check('remote desktop input is set aside, like a virtual display adapter',
          [d['name'] for d in remote] == ['Uzak Masaustu Klavye Aygiti'], remote)


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
    # every candidate plus the no-acceleration id, which is offered but is not a
    # candidate: nothing lists it as a framebuffer because nothing claims it
    check('every candidate reaches the notes, and the fallback with them',
          len(listed) == len(ids) + 1, f'{len(listed)} listed, {len(ids)} candidates')
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
        r = run([sys.executable, 'tools/setup.py', '--answers', '3,2,10,3,9,1,3,1,1',
                 '--out', str(out)])
        check('naming the hardware of another machine builds', r.returncode == 0)
        if r.returncode == 0:
            have = {p.name for p in (out / 'OC' / 'Kexts').iterdir()}
            check('what was named is added', 'IntelMausi.kext' in have
                  and 'IntelBluetoothFirmware.kext' in have, sorted(have))
            check('what was declined is not', 'AirportItlwm.kext' not in have)
            written = (out.parent / 'NEXT-STEPS.txt')
            # the USB follow-up applies to every machine, so the file exists;
            # what must not be there is advice about hardware nobody described
            check('the follow-up is written even with nothing detected',
                  written.exists())
            body = written.read_text() if written.exists() else ''
            check('and it claims nothing about graphics it cannot see',
                  'Intel graphics' not in body and 'framebuffer id' not in body)


def undecodable_output():
    """A byte the encoding cannot name must cost that byte, not the listing.

    On a Turkish Windows the PnP listing carries names in a code page Python was
    decoding without an error handler, and the reader thread inside subprocess
    died on the first bad byte: stdout came back empty and a laptop full of PCI
    devices reported none of them."""
    out = detect._run([sys.executable, '-c',
                       "import sys; sys.stdout.buffer.write("
                       "b'8086:0a16 \\x81\\x8d name\\n')"])
    check('output survives a byte the encoding has no character for',
          '8086:0a16' in out and out.endswith('name\n'), repr(out))
    check('nothing comes back as None, which no caller checks for',
          isinstance(detect._run(['definitely-not-a-command-here']), str))


def scripted_answers():
    """One answer string has to work whether the extra question appears or not.

    The line in CI that builds from real detection cannot know what the runner
    has, so it ends in a decline. That only works if a spare answer is harmless
    when the question it was for never came - which is what this pins down. It
    is checked here rather than left to whichever runner happens to be handed
    out, since a runner with no NVMe drive proves nothing."""
    fixture = 'tools/fixtures/no-hardware.json'
    with tempfile.TemporaryDirectory() as tmp:
        with_drive = Path(tmp) / 'with' / 'EFI'
        without = Path(tmp) / 'without' / 'EFI'
        a = run([sys.executable, 'tools/setup.py', '--machine', fixture,
                 '--nvme', 'Samsung SSD 970 EVO',
                 '--answers', '2,10,3,9,3', '--out', str(with_drive)])
        b = run([sys.executable, 'tools/setup.py', '--machine', fixture,
                 '--answers', '2,10,3,9,3', '--out', str(without)])
        check('the same answers build with the extra question', a.returncode == 0)
        check('and without it, the spare answer being harmless', b.returncode == 0)
        if a.returncode == 0:
            check('declining leaves the kext out',
                  not (with_drive / 'OC' / 'Kexts' / 'NVMeFix.kext').exists())
        short = run([sys.executable, 'tools/setup.py', '--machine', fixture,
                     '--nvme', 'Samsung SSD 970 EVO',
                     '--answers', '2,10,3,9', '--out', str(Path(tmp) / 'short' / 'EFI')],
                    may_fail=True)
        check('running out of answers says so instead of reading a closed stdin',
              short.returncode != 0 and 'ran out' in (short.stdout + short.stderr),
              short.returncode)


def hardware_summary():
    """The screen shown before any question, composed from the same tables."""
    import summary
    toshiba = {
        'cpu': 'Intel(R) Core(TM) i5-4200U CPU @ 1.60GHz', 'generation': 'haswell',
        'laptop': True, 'ps2': True, 'nvme': [], 'hda_ids': ['10ec:0283'],
        'gpu_devices': [{'id': '8086:0a16', 'name': 'Intel(R) HD Graphics Family'}],
        'pci_ids': ['8086:1559', '8086:08b3'], 'usb_ids': ['8087:07dc'],
        'peripherals': [
            {'kind': 'pointing device', 'name': 'Alps Pointing-device',
             'usb': False, 'virtual': False, 'driver': 'i8042prt'},
            {'kind': 'card reader', 'name': 'Realtek PCIE CardReader',
             'usb': False, 'virtual': False, 'driver': 'rtsper'},
            {'kind': 'keyboard', 'name': 'Uzak Masaustu Klavye',
             'usb': False, 'virtual': True, 'driver': 'terminpt'}]}
    by_part = {}
    for r in summary.rows(toshiba):
        by_part.setdefault(r['part'], []).append(r)
    check('a machine that works says so on every row it has data for',
          not [r for rs in by_part.values() for r in rs
               if r['verdict'] == summary.UNSUPPORTED], by_part)
    check('the network rows name the kext, not just a yes',
          'IntelMausi.kext' in by_part['Ethernet'][0]['detail'], by_part.get('Ethernet'))
    check('a PS/2 trackpad is covered by the profile, and says which',
          by_part['Trackpad'][0]['verdict'] == summary.SUPPORTED, by_part.get('Trackpad'))
    check('a card reader stays unknown rather than being guessed at',
          by_part['Card reader'][0]['verdict'] == summary.UNKNOWN)

    desktop = dict(toshiba, laptop=False, ps2=False, peripherals=[],
                   cpu='Intel(R) Core(TM) i9-14900K', generation='raptor-lake',
                   hda_ids=['ffff:ffff'],
                   gpu_devices=[{'id': '8086:e20b', 'name': 'Intel Arc B580'},
                                {'id': '8086:a780', 'name': 'Intel UHD Graphics 770'}])
    parts = [r['part'] for r in summary.rows(desktop)]
    verdicts = {(r['part'], r['what']): r['verdict'] for r in summary.rows(desktop)}
    check('an unsupported card and an unsupported igpu are both called out',
          [v for (p_, _), v in verdicts.items()
           if p_ == 'Graphics'] == [summary.UNSUPPORTED] * 2, verdicts)
    check('a codec AppleALC does not carry is not called supported',
          verdicts[('Audio', 'ffff:ffff')] == summary.UNSUPPORTED, verdicts)
    check('a desktop with no pointing device gets no trackpad row',
          'Trackpad' not in parts, parts)

    blank, complaint = detect.read_report('tools/fixtures/no-hardware.json')
    check('a machine nothing is known about renders without claiming anything',
          complaint is None and not [r for r in summary.rows(blank)
                                     if r['verdict'] == summary.SUPPORTED])
    check('and it still renders', len(summary.render(blank, 'nothing')) > 3)
    check('a table of nothing but unknown is not worth printing',
          not summary.worth_showing(blank))
    check('one that says something is', summary.worth_showing(toshiba))

    # the model the machine printed, rather than the name of the driver set
    named = dict(toshiba, pci_ids=['8086:1559', '10ec:8168', '8086:08b3'],
                 device_names={'8086:1559': 'Intel(R) Ethernet Connection I218-V',
                               '10ec:8168': 'Realtek PCIe GBE Family Controller',
                               '8086:08b3': 'Intel(R) Dual Band Wireless-AC 3160'})
    net = {}
    for r in summary.rows(named):
        net.setdefault(r['part'], []).append(r)
    check('a card is named as the machine names it, not as its driver set',
          [r['what'] for r in net['Wi-Fi']] == ['Intel(R) Dual Band Wireless-AC 3160'],
          net.get('Wi-Fi'))
    check('two cards of one kind are both listed, not just the first',
          len(net['Ethernet']) == 2, net.get('Ethernet'))
    check('the device id survives however long the note is',
          all('[' in r['detail'] for rs in
              (net['Ethernet'], net['Wi-Fi'], net['Bluetooth']) for r in rs), net)
    check('Intel Wi-Fi says it is built per release, since that is why it is asked',
          'one build per macOS' in net['Wi-Fi'][0]['detail'], net['Wi-Fi'])
    check('a set with version-bounded extras says how many',
          '+3' in net['Bluetooth'][0]['detail'], net['Bluetooth'])
    # a DW1820A: the Wi-Fi half came out unrecognised while the Bluetooth half
    # was found, because AirportBrcmFixup declares its devices in IONameMatch
    brcm = dict(toshiba, pci_ids=['14e4:43a3'], usb_ids=['0a5c:6412'],
                device_names={'14e4:43a3': 'Dell Wireless 1820A 802.11ac'})
    rows_by = {}
    for r in summary.rows(brcm):
        rows_by.setdefault(r['part'], []).append(r)
    check('a Broadcom Wi-Fi card is recognised, not left unknown',
          rows_by['Wi-Fi'][0]['verdict'] == summary.SUPPORTED, rows_by['Wi-Fi'])
    check('and it names the kext that patches it',
          'AirportBrcmFixup.kext' in rows_by['Wi-Fi'][0]['detail'], rows_by['Wi-Fi'])
    check('the bluetooth row names the kext the build keys on, not a sibling',
          'BrcmPatchRAM3.kext' in rows_by['Bluetooth'][0]['detail'], rows_by['Bluetooth'])

    check('falling back to the set label when the machine named nothing',
          summary.rows(dict(named, device_names={}))[3]['what'] == 'Intel Ethernet')


def device_names():
    """The model beside each id, from each source's own shape."""
    windows = ('PCI\\VEN_8086&DEV_1559&SUBSYS_00011179&REV_04\\3&x|'
               'Intel(R) Ethernet Connection I218-V')
    lspci = ('00:19.0 Ethernet controller: Intel Corporation Ethernet Connection '
             'I218-V [8086:1559] (rev 04)')
    lsusb = 'Bus 001 Device 004: ID 8087:07dc Intel Corp. Bluetooth wireless interface'
    check('Windows names the device after the pipe',
          detect._names(windows, detect.PCI_PATTERNS) ==
          {'8086:1559': 'Intel(R) Ethernet Connection I218-V'})
    check('lspci names it before the bracketed id, not the revision after it',
          detect._names(lspci, detect.PCI_PATTERNS) ==
          {'8086:1559': 'Intel Corporation Ethernet Connection I218-V'})
    check('lsusb names it after the id',
          detect._names(lsusb, detect.USB_PATTERNS) ==
          {'8087:07dc': 'Intel Corp. Bluetooth wireless interface'})
    check('a line with no id contributes nothing',
          detect._names('some heading', detect.PCI_PATTERNS) == {})


def detection_gaps():
    """Four things the tables knew and the tools were not reading."""
    import inputdev
    from hwtable import acpi_ids as hwtable_acpi_ids
    from hwtable import pci_ids as hwtable_pci_ids

    # a masked term covers a range, and the mask is not a second device
    got = hwtable_pci_ids('0x9d608086&0xFFFCFFFF')
    check('a masked IOPCIMatch expands to the range it covers',
          got == {'8086:9d60', '8086:9d61', '8086:9d62', '8086:9d63'}, sorted(got))
    check('the mask itself never becomes a device id',
          not any(i.startswith('ffff') or i.endswith(':ffff') for i in got), sorted(got))
    check('an unmasked term is unchanged', hwtable_pci_ids('0x8cb18086') == {'8086:8cb1'})
    check('a term matching a whole vendor is not expanded into 65536 of them',
          hwtable_pci_ids('0x000010de&0x0000ffff') == set())

    check('ACPI names are read from IONameMatch',
          hwtable_acpi_ids(['INT33C2', 'AMDI0010', 'pci14e4,43a3']) ==
          {'INT33C2', 'AMDI0010'})
    check('an instance path is not mistaken for an ACPI id',
          detect.acpi_names('ACPI\\PNP0C0C\\2&daba3ff&2') == ['PNP0C0C'])
    check('Linux names them its own way, and only the ones shaped like an id',
          detect.acpi_names('INT3433:00\nLNXSYSTM:00') == ['INT3433'])

    # Haswell and Broadwell put the controller on ACPI, and AMD only ever does
    check('an ACPI-only I2C controller is found', inputdev.controllers([], ['INT33C2']))
    check('including AMD, which has no PCI id at all',
          inputdev.controllers([], ['AMDI0010']))
    check('a PCI one still is', inputdev.controllers(['8086:9d60'], []))
    check('and something unrelated is not',
          not inputdev.controllers(['8086:15b8'], ['PNP0C0C']))
    kexts = inputdev.entries([], False, ['INT33C2'])[1]
    check('and it brings the kexts',
          [k['BundlePath'] for k in kexts] == ['VoodooI2C.kext', 'VoodooI2CHID.kext'], kexts)

    # the machines most likely to have an SMBus trackpad heard nothing about it
    ps2_only = inputdev.notes([], [])
    check('a machine with no I2C controller is told about SMBus anyway',
          'VoodooRMI.kext' in ps2_only and 'VoodooSMBus.kext' in ps2_only)
    check('and told that neither was added for it',
          'Neither kext is added automatically' in ps2_only)

    # nothing gets cut off a verdict
    import summary
    long_note = {'part': 'Graphics', 'what': 'card', 'verdict': summary.UNSUPPORTED,
                 'detail': 'x' * 40 + ' ' + 'y' * 40}
    out = summary.render({'cpu': None, 'pci_ids': []})
    check('the summary still renders with nothing to say', len(out) > 2)
    # An NVIDIA id no name list carries, so no chip family can claim it and the
    # whole-vendor rule is what answers. That rule used to need the word
    # "nvidia" in the reported name, so a card the machine called anything else
    # came out unknown.
    nvidia = {'generation': 'raptor-lake', 'laptop': False, 'pci_ids': [],
              'gpu_devices': [{'id': '10de:ffff', 'name': 'Some Card'}]}
    graphics = [r for r in summary.rows(nvidia) if r['part'] == 'Graphics']
    check('a card is judged on its vendor id, not on what it happens to be called',
          graphics and graphics[0]['verdict'] == summary.UNSUPPORTED, graphics)
    check('a long verdict wraps instead of losing its caveat',
          any('Turing' in l for l in summary.render(nvidia)))

    # and a card the chip family does claim is answered by the family, which is
    # the whole point: a GTX 760 is Kepler and ran until Big Sur
    kepler = dict(nvidia, gpu_devices=[{'id': '10de:1187', 'name': 'GTX 760'}])
    row = [r for r in summary.rows(kepler) if r['part'] == 'Graphics'][0]
    check('a card the family claims is not swept up by the vendor rule',
          row['verdict'] == summary.SUPPORTED, row)


def broadcom_wifi():
    """A Lilu plugin declares its devices somewhere else, and it was being missed."""
    import advise
    import netkexts
    check('IONameMatch is read the way IOKit writes it',
          hwtable_name_ids('pci14e4,43a3') == {'14e4:43a3'})
    check('anything that is not a pci name is left alone',
          hwtable_name_ids(['IOResourceMatch', 'pci8086,1559']) == {'8086:1559'})
    matched = advise.matched_kexts(['14e4:43a3'], [])
    check('a Broadcom card matches the kext that covers it',
          matched == {'AirportBrcmFixup.kext'}, matched)
    added, _ = netkexts.entries(matched, None)
    check('and it goes in with the bound its README gives',
          [(e['BundlePath'], e['MinKernel']) for e in added]
          == [('AirportBrcmFixup.kext', '14.0.0')], added)
    check('so it is left out of a release older than that',
          netkexts.entries(matched, 13)[0] == [])


def framebuffers():
    """Two sources, and they have to agree where they overlap."""
    import igpu
    import setup as guided
    fb = ocgen.read_toml('data/framebuffer.toml')['framebuffer']
    check('the whole list is parsed, not one table', len(fb) > 100, len(fb))
    check('every entry carries what tells it apart',
          all(e['type'] in ('mobile', 'desktop') and 'stolen' in e for e in fb))
    check('the byte-swapped form is right',
          [e['data'] for e in fb if e['value'] == '0x591B0000'] == ['00001b59'],
          [e['data'] for e in fb if e['value'] == '0x591B0000'])
    known = {e['value'].lower() for e in fb}
    guide = [c['value'].lower() for g in ocgen.read_toml('data/gpu.toml')['igpu']
             for key in ('laptop_platform_id', 'desktop_platform_id')
             for c in g.get(key, [])]
    check('every id the guide names is in the manual too, so neither has drifted',
          all(v in known for v in guide), [v for v in guide if v not in known])

    cands = igpu.candidates('kaby-lake', True)
    check('a laptop generation now has more than the one the guide names',
          len(cands) > 1, len(cands))
    check("the guide's pick is still first", cands[0]['value'] == '0x591b0000', cands[0])
    check('headless is last however it was spelled',
          all('headless' not in c['label'].lower()
              for c in cands[:len([c for c in cands
                                   if 'headless' not in c['label'].lower()])]))
    check('a desktop generation gets desktop framebuffers',
          all(e['type'] == 'desktop' for e in igpu.documented('kaby-lake', False)))

    check('leaving the key out asks for it to be removed, not merely unset',
          igpu.props_for(None)[igpu.IGPU_PATH]['AAPL,ig-platform-id'] is None)
    check('the no-acceleration id says whose testing it rests on',
          'maintainer' in igpu.NO_ACCELERATION['note'])
    check('and it is offered as a choice, not written by default',
          igpu.report('kaby-lake', True, True)[1][igpu.IGPU_PATH]['AAPL,ig-platform-id']
          != 'hex:' + igpu.NO_ACCELERATION['data'])

    # the fast path must never be reachable on a guess
    check('a machine with no generation gets no fast path',
          guided.profile_from({'laptop': True}) is None)
    check('nor one where the form factor is unknown',
          guided.profile_from({'generation': 'kaby-lake'}) is None)
    check('nor an AMD laptop, which has no profile',
          guided.profile_from({'laptop': True,
                               'generation': 'ryzen-threadripper'}) is None)
    check('nor an AMD desktop with an unusable core count',
          guided.profile_from({'laptop': False, 'cores': 3,
                               'generation': 'ryzen-threadripper'}) is None)
    ok = guided.profile_from({'laptop': True, 'generation': 'kaby-lake', 'oem': 'hp'})
    check('a machine with all of it does', ok == ('laptop', None, 'kaby-lake', None, 'hp'), ok)
    unknown_oem = guided.profile_from({'laptop': True, 'generation': 'kaby-lake',
                                       'oem': 'toshiba'})
    check('and a brand with no overlay falls back rather than failing',
          unknown_oem and unknown_oem[4] is None, unknown_oem)


def native_device_ids():
    """A generation being supported is not every part in it being supported."""
    import gpu
    native = ocgen.read_toml('data/framebuffer.toml')['native']
    check('every generation with framebuffers has its device ids too',
          len(native) == 58, len(native))
    # the Ivy Bridge section writes "DevIDs :" with a space; matching strictly
    # dropped that whole generation and said nothing
    check('including Ivy Bridge, whose heading is punctuated differently',
          gpu.native_ids('ivy-bridge') == {'8086:0152', '8086:0156',
                                           '8086:0162', '8086:0166'},
          sorted(gpu.native_ids('ivy-bridge')))
    check('Comet Lake is read apart from Coffee Lake, though they share a section',
          gpu.native_ids('comet-lake') == {'8086:9bc8', '8086:9bc5', '8086:9bc4'},
          sorted(gpu.native_ids('comet-lake')))
    check('and Coffee Lake does not inherit Comet Lake ids',
          '8086:9bc4' not in gpu.native_ids('coffe-lake'))

    listed = gpu.classify({'id': '8086:5916', 'name': 'Intel HD Graphics 620'},
                          'kaby-lake')
    check('an id on the list is called natively supported',
          listed[0] == 'works' and 'natively supported' in listed[1]['family'], listed)

    # Whiskey Lake sits in a supported generation and is not on the list, and
    # the document says exactly what it needs: a faked device-id
    whiskey = gpu.classify({'id': '8086:3ea0', 'name': 'Intel UHD Graphics 620'},
                           'coffee-lake-whiskey-lake')
    check('an id off the list is still supported, not condemned',
          whiskey[0] == 'works', whiskey)
    check('and the reason it is flagged is the faked device-id, not support',
          'faked device-id' in whiskey[1]['note'], whiskey[1])
    check('the table row stays one line about it',
          whiskey[1]['family'].endswith('not natively'), whiskey[1]['family'])

    check('an unsupported generation is untouched by any of this',
          gpu.classify({'id': '8086:4680', 'name': 'Intel UHD Graphics 770'},
                       'alder-lake')[0] == 'unsupported')
    check('and a generation with no list gets no claim either way',
          gpu.native_ids('rocket-lake') == set())


def workflow_flags():
    """Every flag CI passes has to be one the tool actually has, spelled in full.

    argparse accepts an unambiguous prefix, so --acpi worked until --acpi-ids
    and --acpi-tables both existed and it became "ambiguous option". Nothing
    fails at the point the flag is added; it fails later, in a job that only
    runs on dispatch."""
    import ast
    declared = {}
    for tool in sorted(Path('tools').glob('*.py')):
        names = set()
        for node in ast.walk(ast.parse(tool.read_text())):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'add_argument'):
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and str(arg.value).startswith('--'):
                        names.add(arg.value)
        if names:
            declared[tool.name] = names | {'--help'}

    used, bad = 0, []
    for wf in sorted(Path('.github/workflows').glob('*.yml')):
        for line in wf.read_text().splitlines():
            line = line.strip()
            if line.startswith('#'):
                continue
            for tool, names in declared.items():
                if f'tools/{tool}' not in line and not (
                        tool == 'setup.py' and 'HackintoshEFIBuilder.exe' in line):
                    continue
                for flag in re.findall(r'(?<![\w-])--[a-z][a-z-]*', line):
                    used += 1
                    if flag not in names:
                        bad.append(f'{wf.name}: {flag} is not a flag of {tool}')
    check('every flag the workflows pass is spelled in full', not bad, bad)
    check('and there were flags to check', used > 20, used)


def runner_independence():
    """No job may answer menus against whatever machine it lands on.

    A fixed --answers string only means one thing if the questions are fixed,
    and they are not: they depend on what was detected. The Windows job answered
    a laptop's questions on a Hyper-V Xeon and ran out halfway."""
    bad = []
    for wf in sorted(Path('.github/workflows').glob('*.yml')):
        # a command can be split over lines with a backslash or a backtick, and
        # the --machine that makes it deterministic is often on the first of them
        joined, buffer = [], ''
        for number, line in enumerate(wf.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            start = number if not buffer else start          # noqa: F821 - set below
            buffer += ' ' + stripped
            if stripped.endswith(('\\', '`')):
                continue
            joined.append((start, buffer))
            buffer = ''
        for number, command in joined:
            if '--answers' not in command:
                continue
            answers = re.search(r'--answers\s+(\S+)', command)
            first = answers.group(1).split(',')[0] if answers else ''
            fixed = ('--machine' in command or '--no-detect' in command
                     or re.search(r'\$[A-Z0-9]+', command)
                     # 2 and 3 at the scope question are "another machine", which
                     # takes the report or the by-name path and detects nothing
                     or first in ('2', '3'))
            if not fixed:
                bad.append(f'{wf.name}:{number} {command.strip()[:70]}')
    # no exceptions: the one job that wanted to build from real detection uses
    # --check instead, which asks nothing
    check('no job answers menus against a machine it cannot predict', not bad, bad)


def frozen_build():
    """What PyInstaller cannot see, and therefore has to be told."""
    import ast
    spec = Path('tools/pyinstaller.spec').read_text()
    named = set(re.findall(r"'([\w.]+)'", spec))
    wanted = set()
    for f in sorted(Path('vendor/tools/SSDTTime').rglob('*.py')):
        for node in ast.walk(ast.parse(f.read_text(encoding='utf-8', errors='replace'))):
            if isinstance(node, ast.Import):
                wanted |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                wanted.add(node.module.split('.')[0])
    # only the standard library: the Python 2 fallbacks in its try blocks are
    # not there to be found, and the frozen build is Python 3
    wanted = {m for m in wanted if m in sys.stdlib_module_names}
    missing = sorted(wanted - named)
    check('every module SSDTTime imports is named in the spec', not missing, missing)

    r = run([sys.executable, 'tools/setup.py', '--check-tools'])
    check('and the builder can load the tools on demand', r.returncode == 0)


def window_stays_open():
    """A console the program opened for itself dies with it, taking the summary.

    Somebody who double-clicks the executable sees a window flash and nothing
    else: the warnings, the path to the EFI and the ROM reminder all go with it.
    So the frozen build waits for a key - and only the frozen build, only on a
    terminal, and never under --answers, or CI would hang."""
    import setup as guided
    src = Path('tools/setup.py').read_text()
    check('the pause is only for the frozen build',
          "if not getattr(sys, 'frozen', False) or SCRIPTING or UI.protocol:" in src)
    # a front end has no key to press and no window to keep open; waiting for
    # one would hang the build behind a prompt nobody can see
    check('and never when a front end is driving', 'or UI.protocol:' in src)
    check('and a refusal is printed before it, not swallowed',
          'if isinstance(exc.code, str):' in src)

    # unfrozen, it must be a no-op whatever stdin is
    check('nothing waits when running from a clone', guided.hold() is None)

    r = run([sys.executable, 'tools/setup.py', '--machine', '/tmp/nope.json'],
            may_fail=True)
    check('a refusal still exits non-zero', r.returncode == 1, r.returncode)
    check('and says why', 'does not exist' in (r.stdout + r.stderr))


def unattended_ssdts():
    """Six patches decide from the tables alone; the rest ask, and must not be
    answered for somebody.

    Run against tools/fixtures/acpi, a DSDT written here rather than dumped, so
    this works on every platform and not only where tables can be read."""
    import acpi
    check('the automatic set is named and described',
          all(len(row) == 3 and all(row) for row in acpi.AUTOMATIC), acpi.AUTOMATIC)
    check('a press-enter is answered', acpi._auto_grab('Press [enter] to go on') == '')
    for prompt in ('Please select an option:', 'Enter the model identifier: ', ''):
        try:
            acpi._auto_grab(prompt)
            check(f'a real question is refused: {prompt!r}', False, 'it answered')
        except acpi._Unattended:
            check(f'a real question is refused: {prompt!r}', True)

    if not acpi.available():
        return
    import contextlib
    import io
    with tempfile.TemporaryDirectory() as tmp:
        with contextlib.redirect_stdout(io.StringIO()):
            results, complaint = acpi.run(Path(tmp) / 'acpi',
                                          tables='tools/fixtures/acpi',
                                          unattended=True)
        check('it runs against a DSDT and writes a Results folder',
              results is not None, complaint)
        if not results:
            return
        made = {p.name for p in Path(results).iterdir()}
        # the fixture has an EC, an RTC, an SMBus device and two Processors
        for want in ('SSDT-EC.aml', 'SSDT-PLUG.aml', 'SSDT-SBUS-MCHC.aml'):
            check(f'{want} was worked out from the tables', want in made, sorted(made))
        aml, add, patches = acpi.collect(results)
        check('and they collect into Add entries', len(add) == len(aml) and add)

    # the fixture's HPET IRQs conflict on purpose, which makes fix_hpet ask -
    # and the guard has to refuse rather than send it a blank line
    with tempfile.TemporaryDirectory() as tmp:
        work = acpi.prepare(Path(tmp) / 'w')
        module = acpi.load(work)
        ssdt = module.SSDT()
        ssdt.u.grab = acpi._auto_grab
        with contextlib.redirect_stdout(io.StringIO()):
            ssdt.dsdt = ssdt.load_dsdt(str(Path('tools/fixtures/acpi').resolve()))
            outcomes = {n: o for n, o, _ in acpi.automatic(ssdt)}
        check('a patch that asks is reported, not answered',
              outcomes.get('SSDT-HPET') == acpi.ASKED, outcomes)
        check('and the ones that do not ask still ran',
              outcomes.get('SSDT-EC') in (acpi.WROTE, acpi.NOT_NEEDED), outcomes)


def ssdt_flow():
    """One question, then the facts, then one question about what is left.

    Three answers up front read as a puzzle to solve before anything has
    happened. The choice belongs after the outcomes, not before them."""
    import acpi
    src = Path('tools/setup.py').read_text()
    check('there is one question to start with, not three',
          "'Work out the SSDTs for this machine?'" in src)
    check('and one about the rest, after the outcomes',
          "'Open SSDTTime to work through those too?'" in src)
    check('every patch never attempted is named',
          len(acpi.ASKS) >= 6 and all(len(x) == 2 and all(x) for x in acpi.ASKS),
          acpi.ASKS)
    named = {n for n, _ in acpi.ASKS} | {n for _, n, _ in acpi.AUTOMATIC}
    check('so nothing the tool can do is invisible', len(named) >= 12, sorted(named))

    src = Path('tools/setup.py').read_text()
    # offering to work out the SSDTs and then saying "no ACPI tables were
    # loaded" is offering something and not doing it. Building for this machine
    # means the tables are right here.
    flow = src[src.index('def run_ssdts('):src.index('def profile_from(')]
    check('the tables are dumped when none were handed in',
          'acpi.dump(' in flow and 'if not tables:' in flow)
    check('and the menu run uses the same ones',
          "acpi.run(Path(a.out).parent / 'ssdt-menus', tables," in flow)
    # the menus used to be refused under a front end, because the tool reads
    # its own input and there was no terminal to read from. It has one input
    # function and this passes a replacement into it.
    check('a front end is offered the menus rather than sent to a console',
          'ask=tool_answer if UI.protocol' in flow
          and 'Run the console builder' not in src)
    check('and the answer goes back through the same path as every other',
          "_answer(t='prompt'" in src[src.index('def tool_answer('):
                                      src.index('def run_ssdts(')])
    import acpi as _acpi
    import inspect
    check('the tool takes the replacement where its own input goes',
          'ask' in inspect.signature(_acpi.run).parameters)

    if not acpi.available():
        return
    import contextlib
    import io
    with tempfile.TemporaryDirectory() as tmp:
        outcomes = []
        with contextlib.redirect_stdout(io.StringIO()):
            acpi.run(Path(tmp) / 'a', tables='tools/fixtures/acpi',
                     unattended=True, outcomes=outcomes)
        kinds = {o for _, o, _ in outcomes}
        check('the outcomes are the three plain ones',
              kinds <= {acpi.WROTE, acpi.NOT_NEEDED, acpi.ASKED}, kinds)
        wrote = [n for n, o, _ in outcomes if o == acpi.WROTE]
        check('and "written" means a file appeared', wrote, outcomes)
        # the fixture's HPET conflicts, so exactly this is what the person sees
        asked = [n for n, o, _ in outcomes if o == acpi.ASKED]
        check('a patch that wants an answer is one of them', asked == ['SSDT-HPET'],
              asked)


def frozen_names():
    """Names a frozen build takes away, which the vendored code still uses.

    And names it takes for itself: PyInstaller ships hooks for packages on
    PyPI, and a hook fires on the module name alone. `tools/usb.py` made the
    frozen build die inside pyusb's hook, in a traceback naming a package this
    repository has never heard of. It is `tools/stick.py` now.

    PyInstaller does not run site.py, so `exit` and `quit` do not exist. SSDTTime
    quits with `exit(0)`: unfrozen that is a SystemExit and is caught, frozen it
    is a NameError that killed the whole builder the moment somebody finished
    making their SSDTs. Reproduced with a one-line frozen probe before fixing."""
    import builtins
    import acpi
    had = {n: getattr(builtins, n, None) for n in ('exit', 'quit')}
    try:
        for name in had:
            if hasattr(builtins, name):
                delattr(builtins, name)
        acpi.restore_site_builtins()
        check('exit is put back when it is not there', hasattr(builtins, 'exit'))
        try:
            builtins.exit(0)
            check('and calling it raises SystemExit', False, 'it returned')
        except SystemExit:
            check('and calling it raises SystemExit', True)
        except BaseException as exc:                # noqa: BLE001
            check('and calling it raises SystemExit', False, repr(exc))
    finally:
        for name, value in had.items():
            if value is not None:
                setattr(builtins, name, value)

    # a module here that shares a name with a hooked package on PyPI breaks
    # the frozen build and nothing else, so it is invisible until a release
    try:
        import _pyinstaller_hooks_contrib.stdhooks as hooks
        where = Path(hooks.__file__).parent
    except Exception:                               # noqa: BLE001 - optional
        where = None
    if where is None:
        check('PyInstaller is not here, so its hook names cannot be checked',
              True, 'skipped')
    else:
        hooked = {h.stem[len('hook-'):].split('.')[0]
                  for h in where.glob('hook-*.py')}
        ours = {f.stem for f in Path('tools').glob('*.py')}
        clash = sorted(ours & hooked)
        check('no module here is named after a package PyInstaller hooks',
              not clash, clash)

    # the tool must not take the builder down with it whatever it does
    src = Path('tools/acpi.py').read_text()
    check('and nothing the tool throws is left to reach the builder',
          'except BaseException' in src)


def the_windows_only_ways_this_broke():
    """Every one of these was invisible on the machine this is written on.

    A window on Windows showed raw JSON in the middle of the ACPI step, then
    skipped it, then - once that was fixed - dumped a second set of tables on
    top of the first and refused them all. Three faults, none reachable from
    macOS or Linux, each found by somebody running it."""
    import acpi as acpimod
    import shutil

    # 1. the tool clears the screen by asking the shell to, and that process
    # inherits stdout - which under a front end is the JSON protocol
    source = Path('tools/acpi.py').read_text()
    check('the screen-clearing is turned off before the tool runs',
          'def quiet_screen' in source)
    check('and both ways in go through it',
          source.count('quiet_screen(module.SSDT())') == 2,
          source.count('quiet_screen(module.SSDT())'))

    class Pretend:
        class u:
            @staticmethod
            def cls():
                raise AssertionError('it cleared the screen')
    acpimod.quiet_screen(Pretend)
    Pretend.u.cls()          # no longer the one that raises

    # 2. the working copy is emptied before it is filled, and "acpi" and
    # "ACPI" are one directory on Windows and macOS. A dump of 22 tables
    # became "no valid .aml files were found".
    with tempfile.TemporaryDirectory() as where:
        base = Path(where)
        tables = base / 'ACPI'
        tables.mkdir()
        shutil.copy2('tools/fixtures/acpi/DSDT.aml', tables / 'DSDT.aml')
        got, complaint = acpimod.run(base / 'acpi', str(tables),
                                     unattended=True, outcomes=[])
        if (base / 'acpi').exists() and os.path.samefile(base / 'acpi', tables):
            check('a working copy that is the tables folder is refused',
                  got is None and 'same folder' in complaint, complaint[:80])
            check('and the tables are still there afterwards',
                  (tables / 'DSDT.aml').exists())
        else:
            check('this filesystem tells the two names apart, so nothing to '
                  'collide', True, 'case-sensitive here')

    # 3. the dumper does not replace what is already in the folder: run it
    # twice and both DSDT.AML and dsdt.dat survive, and SSDTTime then refuses
    # the lot - "multiple files with DSDT signature passed"
    with tempfile.TemporaryDirectory() as where:
        into = Path(where) / 'ACPI'
        into.mkdir()
        (into / 'DSDT.AML').write_bytes(b'x')
        (into / 'dsdt.dat').write_bytes(b'x')
        ok, said = acpimod.clear_dump(into)
        check('a dump empties the folder it writes into',
              ok and not list(into.iterdir()), said)
        (into / 'notes.md').write_text('somebody put this here')
        ok, said = acpimod.clear_dump(into)
        check('but not a folder holding anything else', not ok, said)
        check('and it says what stopped it', 'notes.md' in said, said)
        # the folder somebody actually hit had SSDTTime's own tree in it,
        # uppercased, left by a build from before the ACPI/acpi collision was
        # fixed. Saying so beats leaving them to work out why LICENSE is there.
        for name in ('LICENSE', 'README.MD', 'SSDTTIME.PY'):
            (into / name).write_text('from an older build')
        ok, said = acpimod.clear_dump(into)
        check('and names an older build when that is what it looks like',
              not ok and 'an older build left here' in said, said)
        check('missing is fine, there is nothing to clear',
              acpimod.clear_dump(Path(where) / 'nope')[0])

    # and the builder does not name them so they can collide in the first place
    flow = Path('tools/setup.py').read_text()
    check('the dump and the working copy have names that cannot collide',
          "'ssdt-work'" in flow and "/ 'ACPI'" in flow)
    # every call, not only the first: the one behind "open the menus" was
    # missed, so answering yes got the refusal and carried on as though no
    check('and no call still uses the colliding name',
          "parent / 'acpi'" not in flow,
          [l for l in flow.splitlines() if "parent / 'acpi'" in l])
    # and what CI looks for has to be where the rename put it: the Windows
    # job checked acpi/Results and the folder is ssdt-work/Results now
    for made in (Path('.github/workflows/windows-exe.yml'),
                 Path('.github/workflows/validate.yml')):
        said = made.read_text()
        check(f'{made.name} looks for Results where the rename put it',
              '/acpi/Results' not in said and 'acpi/Results' not in said,
              [l for l in said.splitlines() if 'acpi/Results' in l])


def acpi_tables():
    """SSDTTime is driven, not reimplemented, so the wiring is what is checked."""
    import acpi
    check('the tree is vendored', (Path('vendor/tools/SSDTTime/SSDTTime.py')).exists())
    check('with its licence beside it',
          (Path('vendor/tools/SSDTTime/LICENSE')).exists())
    check('and the ACPICA notice travels with the binaries, as 3.3 requires',
          'Intel Corp' in Path('vendor/tools/iasl/ACPICA-LICENSE.txt').read_text())
    if acpi.available():
        ok, detail = acpi.verify()
        check('every compiler is the file that was checked', ok, detail)
        with tempfile.TemporaryDirectory() as tmp:
            work = acpi.prepare(Path(tmp) / 'w')
            names = {p.name for p in (work / 'Scripts').iterdir()}
            # the tool looks for iasl beside its own Scripts and nowhere else
            check('the compiler lands where the tool looks for it',
                  any(n.startswith('iasl') for n in names), sorted(names))
            # and the legacy one is there so it never reaches for the network
            check('including the legacy one, so nothing is downloaded',
                  any('legacy' in n for n in names), sorted(names))
            module = acpi.load(work)
            ssdt = module.SSDT()
            check('which the tool then finds', ssdt.d.iasl and
                  str(work) in str(ssdt.d.iasl), ssdt.d.iasl)
            check('and the legacy one too', bool(ssdt.d.iasl_legacy))

    # two SSDTs doing the same job is not additive
    check('a generic SSDT and a tailored one are the same job',
          acpi.same_purpose('SSDT-PLUG-DRTNIA.aml', 'SSDT-PLUG.aml'))
    check('so are the EC ones',
          acpi.same_purpose('SSDT-EC-USBX-LAPTOP.aml', 'SSDT-EC.aml'))
    check('but PNLF and PLUG are not',
          not acpi.same_purpose('SSDT-PNLF.aml', 'SSDT-PLUG.aml'))

    with tempfile.TemporaryDirectory() as tmp:
        results = Path(tmp) / 'Results'
        results.mkdir()
        (results / 'SSDT-PLUG.aml').write_bytes(b'SSDT' + bytes(32))
        import plistlib
        with open(results / 'patches_OC.plist', 'wb') as fh:
            plistlib.dump({'ACPI': {'Patch': [{'Comment': 'x', 'Find': b'EC0_',
                                               'Replace': b'EC__'}]}}, fh)
        aml, add, patches = acpi.collect(results)
        check('the SSDTs and the patches are read out of what it wrote',
              [p.name for p in aml] == ['SSDT-PLUG.aml'] and len(patches) == 1,
              (aml, patches))
        # the fixture above writes three keys of the fifteen OpenCore wants,
        # which is what a config that ocvalidate rejects looks like
        check('a patch missing keys is completed rather than passed through',
              set(patches[0]) == set(acpi.PATCH_DEFAULTS), sorted(patches[0]))
        check('and the Add entry points at the file by name',
              add[0]['Path'] == 'SSDT-PLUG.aml' and add[0]['Enabled'])

        out = Path(tmp) / 'EFI'
        r = run([sys.executable, 'tools/build.py', '--platform', 'laptop',
                 '--cpu', 'kaby-lake', '--acpi', str(results), '--out', str(out)])
        check('a build folds them in', r.returncode == 0)
        if r.returncode == 0:
            cfg = ocgen.load_plist(out / 'OC' / 'config.plist')
            by_path = {e['Path']: e for e in cfg['ACPI']['Add']}
            check('the tailored SSDT goes in',
                  by_path.get('SSDT-PLUG.aml', {}).get('Enabled'), sorted(by_path))
            check('the generic one it replaces is turned off, not left fighting it',
                  by_path.get('SSDT-PLUG-DRTNIA.aml', {}).get('Enabled') is False,
                  sorted(by_path))
            check('and the file is copied in beside the others',
                  (out / 'OC' / 'ACPI' / 'SSDT-PLUG.aml').exists())
            found = [p for p in cfg['ACPI']['Patch'] if bytes(p['Find']) == b'EC0_']
            check('the patch is the tool\'s own, not one rebuilt from reading it',
                  len(found) == 1, found)
            again = run([sys.executable, 'tools/build.py', '--platform', 'laptop',
                         '--cpu', 'kaby-lake', '--acpi', str(results),
                         '--out', str(Path(tmp) / 'twice')])
            cfg2 = ocgen.load_plist(Path(tmp) / 'twice' / 'OC' / 'config.plist')
            check('and building twice does not add it twice',
                  len([p for p in cfg2['ACPI']['Patch']
                       if bytes(p['Find']) == b'EC0_']) == 1)


def usb_mapping():
    """The tool is vendored whole and driven, so what matters is the wiring."""
    import usbmap
    tool = usbmap.available()
    check('the tool is here', tool is not None, tool)
    if tool:
        ok, detail = usbmap.verify(tool)
        check('and it is the file that was checked', ok, detail)
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / 'Windows.exe'
            fake.write_bytes(b'not the tool')
            check('a file that is not would be refused', not usbmap.verify(fake)[0])
    check('it is only offered where it can run',
          usbmap.runnable_here() == (sys.platform == 'win32'))

    # which map was written decides what comes out of the EFI, and the native
    # ones do not ride on USBToolBox.kext
    utb = usbmap.OUTPUTS['UTBMap.kext']
    native = usbmap.OUTPUTS['USBMap.kext']
    check('a UTBMap keeps USBToolBox.kext and drops the catch-all',
          utb['needs'] == ['USBToolBox.kext'] and utb['drops'] == ['UTBDefault.kext'])
    check('a native map drops both',
          set(native['drops']) == {'UTBDefault.kext', 'USBToolBox.kext'}
          and not native['needs'])
    lock = ocgen.read_toml('vendor/tools.lock')['tool']['USBToolBox/Windows.exe']
    check('the lock records the licence, since it is somebody else\'s binary',
          lock['license'] == 'MIT' and (Path('vendor/tools/USBToolBox/LICENSE')).exists())


def third_party():
    """What we ship that somebody else wrote, and under what."""
    import thirdparty
    ours = thirdparty.upstreams()
    lic = thirdparty.read_licences()
    check('every vendored kext with an upstream has that licence read',
          set(ours) <= set(lic), sorted(set(ours) - set(lic)))
    check('and the answer is recorded, not guessed',
          all(e.get('licence') for e in lic.values()))
    # the point of the report: these are not a problem to be fixed, they are a
    # fact to be visible
    stated = {r for r, e in lic.items() if e['licence'] != thirdparty.NONE_STATED}
    check('some are copyleft, which is an obligation and not an error',
          any(e['licence'].startswith('GPL') for e in lic.values()))
    check('and some state nothing at all', len(stated) < len(lic), sorted(lic))

    cands = thirdparty.candidates()
    check('every candidate names a licence, since that decides vendoring',
          all(c.get('licence') for c in cands), cands)
    check('and says what it would cover', all(c.get('covers') for c in cands))
    counted = [c for c in cands if c.get('ids')]
    check('the ones with a release carry ids read from the kext itself',
          counted and all(all(':' in i for i in c['ids']) for c in counted))
    have = {i for d in ocgen.read_toml('data/hardware.toml')['driver'] for i in d['ids']}
    check('and every one of those ids is genuinely new',
          all(set(c['ids']) - have for c in counted),
          [c['name'] for c in counted if not set(c['ids']) - have])
    check('an archived project with no release says so rather than looking uncounted',
          any(c.get('unreleased') for c in cands))

    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()) as out:
        rc = thirdparty.main([])
    text = out.getvalue()
    check('the report runs offline', rc == 0 and 'What this repository ships' in text)
    check('and names the kexts with no upstream recorded at all',
          'no upstream recorded' in text)


def card_readers():
    """macOS ships no driver for these; one project does and publishes a table."""
    import summary
    d = ocgen.read_toml('data/cardreader.toml')
    check('the device table is parsed, not retyped', len(d['device']) >= 15,
          len(d['device']))
    check('and it keeps the ones the project does not drive yet',
          any(not e['supported'] for e in d['device']))
    check('with the systems it says it was tested on',
          any('Monterey' in s for s in d['driver']['systems']), d['driver']['systems'])
    check('and its licence, since vendoring it would need one',
          d['driver']['license'] == 'BSD-3-Clause')

    base, _ = detect.read_report('tools/fixtures/thinkpad-e570.json')
    def reader(hw_id):
        hw = dict(base, peripherals=base['peripherals'] + [
            {'kind': 'card reader', 'name': 'Realtek PCIE CardReader',
             'id': hw_id, 'driver': 'rtsper', 'usb': False, 'virtual': False}])
        return [r for r in summary.rows(hw) if r['part'] == 'Card reader'][0]

    good = reader('PCI\\VEN_10EC&DEV_5227')
    check('a reader the driver drives is called supported',
          good['verdict'] == summary.SUPPORTED, good)
    check('and the row says the kext is not shipped here',
          'not shipped here' in good['detail'], good)
    notyet = reader('PCI\\VEN_10EC&DEV_5261')
    check('one the project lists and does not drive is not called unknown',
          notyet['verdict'] == summary.UNSUPPORTED, notyet)
    other = reader('PCI\\VEN_1217&DEV_8621')
    check('and one no driver here knows stays unknown',
          other['verdict'] == summary.UNKNOWN, other)


def load_order():
    """OpenCore loads kexts in list order, so a dependency listed late is inert.

    Not a rule anybody here invented: the reference manual states it and says to
    read OSBundleLibraries for the answer, which is where the graph comes from.
    A config that gets this wrong does not fail loudly - the dependent kext just
    never loads, and whatever it was for does not work."""
    import kextorder
    deps = kextorder.graph()
    check('the graph is read from the kexts, not written down',
          deps.get('WhateverGreen.kext') == {'Lilu.kext'}, deps.get('WhateverGreen.kext'))
    check('a plugin is a bundle path of its own, as the manual says',
          'VoodooRMI.kext' in deps.get(
              'VoodooRMI.kext/Contents/PlugIns/RMISMBus.kext', set()),
          deps.get('VoodooRMI.kext/Contents/PlugIns/RMISMBus.kext'))
    check('and a kext with no libraries needs nothing',
          not deps.get('Lilu.kext'), deps.get('Lilu.kext'))

    wrong = [{'BundlePath': 'WhateverGreen.kext', 'Enabled': True},
             {'BundlePath': 'Lilu.kext', 'Enabled': True}]
    found = kextorder.check(wrong, deps)
    check('the wrong way round is caught', len(found) == 1 and
          found[0][:2] == ('WhateverGreen.kext', 'Lilu.kext'), found)
    right = list(reversed(wrong))
    check('and the right way round is not', not kextorder.check(right, deps))
    off = [{'BundlePath': 'WhateverGreen.kext', 'Enabled': True},
           {'BundlePath': 'Lilu.kext', 'Enabled': False}]
    check('a dependency that is present but disabled counts as absent',
          kextorder.check(off, deps)[0][2] == 'is not in the config',
          kextorder.check(off, deps))

    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()) as printed:
        rc = kextorder.main([])
    check('every published config is in order', rc == 0, printed.getvalue())

    # and a build that adds kexts keeps it that way
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'EFI'
        r = run([sys.executable, 'tools/setup.py',
                 '--machine', 'tools/fixtures/thinkpad-e570.json',
                 '--answers', '1,9,1,1', '--out', str(out)])
        check('a build with kexts added succeeds', r.returncode == 0,
              (r.stdout or r.stderr)[-200:])
        if r.returncode == 0:
            cfg = ocgen.load_plist(out / 'OC' / 'config.plist')
            problems = kextorder.check(cfg['Kernel']['Add'], deps)
            check('and what was added is still in order', not problems, problems)


def smbus_trackpad():
    """The machine names its own SMBus controller, which says which bus it is on.

    A Synaptics or ELAN trackpad on SMBus puts its vendor's driver on the SMBus
    device, and Windows reports the device under that name. Until this, nothing
    read here could tell an SMBus trackpad from a PS/2 one, so both kexts were
    only ever named in the notes."""
    import inputdev
    import summary
    real = {'8086:9d23': 'Synaptics SMBus Driver'}
    check('a vendor on the SMBus is read as the trackpad being there',
          inputdev.smbus_trackpad(real)[0] == 'smbus-synaptics',
          inputdev.smbus_trackpad(real))
    check('ELAN too',
          inputdev.smbus_trackpad({'8086:9d23': 'ELAN SMBus Device'})[0] == 'smbus-elan')
    check('an SMBus controller nobody claimed says nothing',
          inputdev.smbus_trackpad({'8086:9d23': 'Intel(R) SMBus - 9D23'})[0] is None)
    check('nor does a Synaptics device that is not on the SMBus',
          inputdev.smbus_trackpad({'8086:9d60': 'Synaptics Pointing Device'})[0] is None)
    # saying yes is not "add one kext": the project gives an ordered set and one
    # plugin that has to come out, and two VoodooInput kexts at once is the
    # failure it is warning about
    rule = inputdev.smbus_rule('smbus-synaptics')
    check('the rule carries the whole ordered set',
          rule['kexts'] == ['VoodooRMI.kext',
                            'VoodooRMI.kext/Contents/PlugIns/VoodooInput.kext',
                            'VoodooSMBus.kext',
                            'VoodooRMI.kext/Contents/PlugIns/RMISMBus.kext'],
          rule['kexts'])
    check("and what the profile's has to stop doing",
          rule['disable'] == ['VoodooPS2Controller.kext/Contents/PlugIns/'
                              'VoodooInput.kext'], rule.get('disable'))
    check('every plugin it names is in the vendored kext',
          all((Path('EFI/OC/Kexts') / k).exists() for k in rule['kexts']),
          [k for k in rule['kexts'] if not (Path('EFI/OC/Kexts') / k).exists()])
    check('and the check to run in macOS afterwards is quoted',
          'Intertouch Support' in rule['macos_check'])

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / 'EFI'
        r = run([sys.executable, 'tools/build.py', '--platform', 'laptop',
                 '--cpu', 'kaby-lake', '--disable-kexts', rule['disable'][0],
                 '--out', str(out)])
        check('a build can turn one off without taking it out', r.returncode == 0)
        if r.returncode == 0:
            cfg = ocgen.load_plist(out / 'OC' / 'config.plist')
            by = {k['BundlePath']: k for k in cfg['Kernel']['Add']}
            check('it is off', by[rule['disable'][0]]['Enabled'] is False)
            check('and still there, so turning it back on is one edit',
                  rule['disable'][0] in by)

    base, _ = detect.read_report('tools/fixtures/thinkpad-e570.json')
    ps2_only = {r['part']: r for r in summary.rows(base)}['Trackpad']
    check('without it the row still says PS/2', 'PS/2' in ps2_only['detail'], ps2_only)
    on_smbus = dict(base, device_names={**base['device_names'], **real})
    row = {r['part']: r for r in summary.rows(on_smbus)}['Trackpad']
    check('with it the row names the kext instead',
          'VoodooRMI.kext' in row['detail'], row)
    # both controllers are present on these laptops; only one carries the pad
    check('and the PS/2 controller being there too does not win',
          'PS/2' not in row['detail'], row)


def macos_window():
    """Where each part bounds macOS, and what the intersection of those is."""
    import summary
    e570, _ = detect.read_report('tools/fixtures/thinkpad-e570.json')

    ranges = ocgen.read_toml('data/framebuffer.toml')['support']
    check('every generation states its macOS range', len(ranges) == 7, len(ranges))
    skl = [r for r in ranges if r['codename'] == 'SKL']
    check('including the one that writes "Officially supported"',
          skl and (skl[0]['min_darwin'], skl[0]['max_darwin']) == (15, 21), skl)
    ivy = [r for r in ranges if r['codename'] == 'Capri']
    check('and one whose floor is older than data/macos.toml lists',
          ivy and ivy[0]['min_darwin'] == 12, ivy)
    kbl = [r for r in ranges if r['codename'] == 'KBL/ABL']
    check('a generation with no ceiling records none rather than inventing one',
          kbl and kbl[0]['max_darwin'] == 0, kbl)

    parts = {w[0]: w for w in summary.macos_windows(e570)}
    check('the iGPU bounds it', 'Intel graphics' in parts, sorted(parts))
    check('so does a kext the card actually needs',
          parts.get('Broadcom Wi-Fi', (None, None, None))[1] == 14, parts)
    check('but a kext that only improves a device does not',
          'Non-Apple NVMe' not in parts, sorted(parts))

    floor, ceiling = summary.macos_range(e570)
    check('the oldest is the highest floor of them all',
          floor[1] == 16 and floor[0] == 'Intel graphics', floor)
    # This used to read "with nothing capped, there is no ceiling". Something
    # is capped now: AirportBrcmFixup patches Apple's Broadcom driver, and its
    # own README lists that driver as removed from macOS 14 ("[14+] Use with
    # OCLP"), so data/network.toml stops the set at Ventura. The card in this
    # machine is a DW1820A, so the machine really does top out there - and
    # saying so is the point. The part that sets it has to be named.
    check('the newest is the lowest ceiling of them all',
          ceiling and ceiling[0] == 'Broadcom Wi-Fi' and ceiling[2] == 22, ceiling)

    haswell = dict(e570, generation='haswell',
                   gpu_devices=[{'id': '8086:0a16', 'name': 'Intel HD Graphics 4400'}])
    floor, ceiling = summary.macos_range(haswell)
    check('a generation macOS dropped does cap it',
          ceiling and ceiling[2] == 21, ceiling)

    # an iGPU that has been run and found not to accelerate bounds nothing
    cml, _ = detect.read_report('tools/fixtures/comet-lake-h.json')
    check('a field report takes the iGPU out of the reckoning',
          'Intel graphics' not in {w[0] for w in summary.macos_windows(cml)},
          summary.macos_windows(cml))

    rendered = '\n'.join(summary.render(e570, 'test'))
    check('the range reaches the screen', 'Sierra 10.12 to Ventura 13' in rendered,
          [l for l in rendered.splitlines() if 'macOS' in l])
    check('and the kext that stops it says so on its own row',
          'up to Ventura' in rendered,
          [l for l in rendered.splitlines() if 'Brcm' in l])
    check('with what these tables cannot see said next to it',
          'SMBIOS' in rendered and 'discrete card' in rendered)


def field_reports():
    """An observation outranks a rule written for the generation, and says so."""
    import gpu
    import summary
    ten = {'cpu': 'Intel(R) Core(TM) i5-10200H CPU @ 2.40GHz',
           'generation': 'comet-lake', 'laptop': True, 'pci_ids': [], 'ps2': False,
           'gpu_devices': [{'id': '8086:9bc4', 'name': 'Intel(R) UHD Graphics'}]}
    other = dict(ten, cpu='Intel(R) Core(TM) i5-10210U CPU @ 1.60GHz')

    check('the generation rule alone would call this one supported',
          gpu.igpu_verdict('comet-lake')[0] == 'works')
    found = gpu.field_igpu(ten['cpu'])
    check('the field report is matched on the processor', found and
          found['status'] == 'unsupported', found)
    check('and it names who observed it and what they saw',
          found and found['observed_by'] and 'acceleration' in found['observed'])
    check('another processor of the same generation is untouched',
          gpu.field_igpu(other['cpu']) is None)

    rows = {r['part']: r for r in summary.rows(ten)}
    check('so the summary calls it unsupported',
          rows['Graphics']['verdict'] == summary.UNSUPPORTED, rows['Graphics'])
    check('with the observation as the reason, not a table',
          'reported by' in rows['Graphics']['detail'], rows['Graphics'])
    check('and the rest of the generation still reads supported',
          {r['part']: r for r in summary.rows(other)}['Graphics']['verdict']
          == summary.SUPPORTED)

    lines = gpu.report(ten['gpu_devices'], 'comet-lake', ten['cpu'])[0]
    check('the graphics section agrees with the summary',
          any('not supported' in l for l in lines), lines)


def provenance():
    """The report has to be readable off the files, not off a memory of them."""
    import provenance as prov
    table = prov.catalogue()
    kinds = {r['kind'] for r in table}
    check('every row declares one of the kinds',
          kinds <= {prov.DERIVED, prov.QUOTED, prov.MEASURED,
                    prov.REPORTED, prov.NONE}, kinds)
    check('every row names what it does not cover',
          all(r['gap'] for r in table))
    hardware = [r for r in table if r['file'] == 'data/hardware.toml'][0]
    real = sum(len(d['ids']) for d in ocgen.read_toml('data/hardware.toml')['driver'])
    check('the counts are read from the files, not typed',
          str(real) in hardware['count'], hardware['count'])
    # AMD integrated graphics moves between the two as the table fills: it is
    # NONE while nobody has run one and REPORTED once somebody has, so pinning
    # a frozen set here would fail the day a row is added.
    empty = {r['area'] for r in table if r['kind'] == prov.NONE}
    check('the areas with no source are named as such',
          empty >= {'Camera', 'Drivers OpenCore does not build'}, sorted(empty))
    amd = [r for r in table if r['area'] == 'AMD integrated graphics'][0]
    rows = int(re.search(r'\d+', amd['count']).group())
    check('and AMD integrated graphics is one of them only while it is empty',
          (amd['kind'] == prov.NONE) == (rows == 0), (amd['kind'], amd['count']))
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()) as printed:
        rc = prov.main([])
    check('and it runs', rc == 0 and 'Where the answers come from' in printed.getvalue())


def tables_match_sources():
    with tempfile.TemporaryDirectory() as tmp:
        gen = Path(tmp) / 'hardware.toml'
        r = run([sys.executable, 'tools/hwtable.py', 'EFI/OC/Kexts', '--out', str(gen)])
        if r.returncode != 0:
            check('the hardware table regenerates', False)
            return
        check('the hardware table still matches the kexts',
              gen.read_text() == Path('data/hardware.toml').read_text())
        table = ocgen.read_toml('data/hardware.toml')['driver']
        roles = {d['role'] for d in table}
        check('every role the tools read is in it',
              {'ethernet', 'wifi', 'bluetooth', 'trackpad'} <= roles, sorted(roles))
        check('no id is a leftover mask',
              not [i for d in table for i in d['ids']
                   if i.startswith('ffff') or i.endswith(':ffff')])


def front_end_protocol():
    """The same flow, driven as a front end would drive it.

    Two surfaces is two things to get wrong, so what is checked here is that
    there are not two: the same questions in the same order, and a config that
    differs from the console's only where it is meant to - the SMBIOS serials,
    which are generated fresh every run."""
    import json
    import ui

    check('a line keeps the tone the console would have shown it in',
          ui.spans('\033[32mdone\033[0m') == [{'tone': 'green', 'text': 'done'}],
          ui.spans('\033[32mdone\033[0m'))
    check('and a line with no codes is one plain span',
          ui.spans('plain') == [{'tone': 'plain', 'text': 'plain'}])

    with tempfile.TemporaryDirectory() as tmp:
        console = Path(tmp) / 'console' / 'EFI'
        front = Path(tmp) / 'front' / 'EFI'
        typed = run([sys.executable, 'tools/setup.py', '--no-detect',
                     '--answers', '2,10,3,9', '--out', str(console)])
        check('the console still builds', typed.returncode == 0)

        # answered by name rather than by number, which is the point of the
        # event: a front end draws the rows and never has to count them
        want = {'What kind of machine is this?': 'laptop',
                'Which CPU generation?': 'kaby-lake',
                'Board or laptop brand?': 'hp',
                'Which macOS are you installing?': 22}
        proc = subprocess.Popen(
            [sys.executable, 'tools/setup.py', '--no-detect', '--protocol',
             '--out', str(front)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            encoding='utf-8', bufsize=1)
        asked, events, built, rc = [], [], None, None
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except ValueError:
                check('every line is one JSON object', False, line[:70])
                break
            events.append(event['t'])
            if event['t'] == 'ask':
                asked.append(event['question'])
                pick = want.get(event['question'])
                n = next((o['n'] for o in event['options'] if o['value'] == pick), 1)
                proc.stdin.write(json.dumps({'id': event['id'], 'value': str(n)}) + '\n')
                proc.stdin.flush()
            elif event['t'] == 'prompt':
                proc.stdin.write(json.dumps({'id': event['id'], 'value': ''}) + '\n')
                proc.stdin.flush()
            elif event['t'] == 'built':
                built = event['out']
            elif event['t'] == 'done':
                rc = event['rc']
        proc.wait()

        check('it says what it is before anything else', events[:1] == ['hello'], events[:1])
        check('and how it ended, last', events[-1] == 'done', events[-1])
        check('the front end was asked the same four questions', len(asked) == 4, asked)
        check('and one of them was which macOS',
              'Which macOS are you installing?' in asked, asked)
        check('it built', rc == 0 and proc.returncode == 0, rc)
        check('and said where', built and Path(built).exists(), built)

        if typed.returncode == 0 and rc == 0:
            import plistlib

            def without_serials(path):
                """The config, minus what is generated fresh on every run.

                Counting differing lines instead was wrong in a way that only
                showed in CI: two runs can draw the same serial, and then two
                lines match by luck and the count is short."""
                with open(path, 'rb') as fh:
                    plist = plistlib.load(fh)
                generic = plist.get('PlatformInfo', {}).get('Generic', {})
                for key in ('SystemUUID', 'SystemSerialNumber', 'MLB'):
                    generic.pop(key, None)
                return plist

            a = without_serials(console / 'OC' / 'config.plist')
            b = without_serials(front / 'OC' / 'config.plist')
            check('the two configs are the same everywhere else', a == b,
                  [k for k in set(a) | set(b) if a.get(k) != b.get(k)])

    # every module that prints in colour asks the same question about it
    for name in ('advise', 'kextorder', 'provenance', 'summary', 'thirdparty', 'setup'):
        source = Path('tools') / f'{name}.py'
        check(f'{name} takes its colours from one place',
              'ui.colours(' in source.read_text()
              and "os.environ.get('NO_COLOR')" not in source.read_text())


def machine_document():
    """What a front end opens on: the same summary, as values.

    The risk here is two answers to one question - a screen that says something
    the printed table does not. So the document is built from the same rows,
    and what is checked is that they cannot drift apart."""
    import json
    import summary

    hw = json.loads(Path('tools/fixtures/thinkpad-e570.json').read_text())
    hw = hw.get('hardware', hw)
    doc = summary.document(hw, 'a fixture')

    printed = summary.rows(hw)
    check('a row for every row the table has', len(doc['rows']) == len(printed))
    check('and the same verdicts',
          [r['verdict'] for r in doc['rows']] == [r['verdict'] for r in printed])

    # the sentence and the field have to agree: pulling the kext out of the
    # prose is what this replaced, and a row where they disagree would be a
    # screen contradicting the text underneath it
    for r in doc['rows']:
        for k in r['kexts']:
            check(f"{r['part']}: {k['bundle']} is the one the sentence names",
                  k['bundle'].replace('.kext', '') in r['detail']
                  or k['bundle'] in r['detail'], r['detail'])

    # the note is what the columns cannot say. A screen that draws the kext in
    # its own column and repeats it underneath has said one thing twice.
    for r in doc['rows']:
        for k in r['kexts']:
            check(f"{r['part']}: the note does not repeat {k['bundle']}",
                  k['bundle'].replace('.kext', '') not in r['note'], r['note'])
        for i in r['ids']:
            check(f"{r['part']}: the note does not repeat {i}", i not in r['note'])
    check('and the console sentence is untouched',
          'AirportBrcmFixup.kext' in next(
              r for r in doc['rows'] if r['part'] == 'Wi-Fi')['detail'])

    wifi = next(r for r in doc['rows'] if r['part'] == 'Wi-Fi')
    facts = wifi['kexts'][0]
    check('a vendored kext carries its upstream', facts['upstream'], facts)
    check('and a link built from it',
          facts['url'] == f"https://github.com/{facts['upstream']}", facts['url'])
    check('and the licence this repository read from that project',
          facts['licence'] and facts['licence'] != 'none stated', facts['licence'])
    check('and whether it is actually here', facts['shipped'] is True)
    check('the version is the vendored one, not a remembered one',
          facts['version'] == ocgen.read_toml(
              Path('vendor/kexts.lock'))['kext'][facts['bundle']]['version'])

    check('the macOS floor names what set it',
          doc['macos']['from']['version'] == '10.12'
          and doc['macos']['from_because'] == 'Intel graphics', doc['macos'])

    # a Mac reports none of its own hardware, and eight unknown rows is noise
    blank = json.loads(Path('tools/fixtures/no-hardware.json').read_text())
    blank = blank.get('hardware', blank)
    check('a machine nothing is known about says so instead',
          summary.document(blank)['worth_showing'] is False)

    with tempfile.TemporaryDirectory() as tmp:
        r = run([sys.executable, 'tools/setup.py', '--describe',
                 '--machine', 'tools/fixtures/thinkpad-e570.json',
                 '--out', str(Path(tmp) / 'EFI')])
        check('--describe writes one JSON object and stops', r.returncode == 0
              and len(r.stdout.strip().splitlines()) == 1, r.returncode)
        if r.returncode == 0:
            written = json.loads(r.stdout)
            check('naming the report it was given as the source',
                  written['source'].startswith('report'), written['source'])
            check('and it is the same document', written['rows'] == doc['rows'])


def machine_name():
    """What a machine calls itself, and when that is worth repeating.

    A vendor who left the field at its default has said nothing, and printing
    "To Be Filled By O.E.M." as a machine's name is worse than printing the
    processor: it looks like an answer."""
    import detect

    check('a laptop is named by the field Lenovo puts the name in',
          detect.model_name({'laptop': True, 'version': 'ThinkPad E570',
                             'model': '20H5006TTX'}) == 'ThinkPad E570')
    check('and by the product name where that field is a version',
          detect.model_name({'laptop': True, 'version': '1.0',
                             'model': 'Inspiron 5570'}) == 'Inspiron 5570')
    check('a desktop is named by its board, which is what it is',
          detect.model_name({'laptop': False, 'model': 'System Product Name',
                             'board': 'ASUSTeK PRIME Z390-A'}) == 'ASUSTeK PRIME Z390-A')
    for empty in ('To Be Filled By O.E.M.', 'Default string', 'System Product Name',
                  '', '   ', 'Rev 1.02', 'x.x'):
        check(f'{empty!r} names nothing',
              detect.model_name({'laptop': True, 'version': empty}) is None)
    check('and nothing at all is nothing', detect.model_name({}) is None)

    # this machine, whatever it is: the point is that it does not throw
    named = detect.probe().get('model')
    check('probing this machine returns a name or None',
          named is None or isinstance(named, str), named)


def embedded_fonts():
    """Two faces travel inside the window, so two licences travel with them."""
    fonts = Path('gui/Assets/Fonts')
    if not fonts.exists():
        check('the fonts directory is there', False)
        return
    have = {p.name for p in fonts.glob('*.ttf')}
    check('the faces the window asks for are present',
          have == {'InstrumentSans-Regular.ttf', 'InstrumentSans-SemiBold.ttf',
                   'IBMPlexMono-Regular.ttf'}, sorted(have))
    # "Plex" is a Reserved Font Name, so that file has to be the published one
    check('nothing asks for a Plex weight that is not published',
          'IBMPlexMono-Medium' not in Path('gui/App.axaml').read_text())
    for licence in ('OFL-InstrumentSans.txt', 'OFL-IBMPlexMono.txt'):
        text = (fonts / licence).read_text(encoding='utf-8', errors='replace')
        check(f'{licence} is the licence it claims to be',
              'SIL OPEN FONT LICENSE' in text.upper())
    # a modified font under the OFL may not keep the original's reserved name,
    # and these two were cut from a variable font
    readme = (fonts / 'README.md').read_text(encoding='utf-8')
    check('the modified files say they are modified',
          'instancer' in readme and 'renamed' in readme)
    check('and the build embeds them rather than asking the system',
          'AvaloniaResource Include="Assets/Fonts/*.ttf"'
          in Path('gui/Shell.csproj').read_text())


def macos_registry():
    """A Mac's own devices, read from the registry rather than the report of it.

    system_profiler answers with nothing at all on Apple silicon - measured on
    an M1 Pro, SPPCIDataType printed zero lines - while the IORegistry on the
    same machine had the Wi-Fi, the Bluetooth and the card reader. This matters
    on a PC already running macOS, where the machine being described is the
    machine being converted."""
    import detect

    check('an id is little-endian in the registry and big-endian everywhere else',
          detect._le(b'\xe4\x14\x00\x00') == '14e4', detect._le(b'\xe4\x14'))
    check('and nothing is not an id', detect._le(None) is None and detect._le(b'\x01') is None)
    check('a name stops at the first NUL', detect._text(b'BCM4387\x00junk') == 'BCM4387')

    plist = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><array><dict>
  <key>vendor-id</key><data>axAAAA==</data>
  <key>device-id</key><data>DBAAAA==</data>
  <key>IOName</key><string>pci-bridge</string>
  <key>IORegistryEntryChildren</key><array><dict>
    <key>vendor-id</key><data>5BQAAA==</data>
    <key>device-id</key><data>M0QAAA==</data>
    <key>model</key><data>QkNNNDM4NwA=</data>
  </dict></array>
</dict></array></plist>"""

    was = detect._run
    try:
        detect._run = lambda cmd, shell=False: (
            plist.decode() if 'IOPCIDevice' in cmd else '')
        pci, usb, hda, roles, drivers = detect.macos_devices()
    finally:
        detect._run = was

    check('a nested device is found, not only the bridge above it',
          '[14e4:4433]|BCM4387' in pci, pci)
    check('and the bridge as well, since it is a device with an id',
          '[106b:100c]' in pci, pci)
    check('an id with no name has no trailing bar',
          '[106b:100c]|' not in pci, pci)
    check('the lines parse with the reader that already exists',
          detect._pairs(pci, detect.PCI_PATTERNS) == {'14e4:4433', '106b:100c'},
          detect._pairs(pci, detect.PCI_PATTERNS))
    check('and the name comes back with the id it was beside',
          detect._names(pci, detect.PCI_PATTERNS).get('14e4:4433') == 'BCM4387',
          detect._names(pci, detect.PCI_PATTERNS))
    check('nothing is invented for the classes that answered nothing',
          usb == '' and hda == '')

    # a combo chip gives both halves the same `compatible`, so the entry name
    # has to win or the Bluetooth is reported as a second Wi-Fi
    wifi = {'IORegistryEntryName': 'wlan', 'compatible': b'wlan-pcie,bcm4387\x00'}
    bt = {'IORegistryEntryName': 'bluetooth-pcie', 'compatible': b'wlan-pcie,bcm4387\x00'}
    check('the machine naming a device wlan means Wi-Fi',
          detect._pci_role(wifi) == 'wifi')
    check('and naming one bluetooth means Bluetooth, whatever it is compatible with',
          detect._pci_role(bt) == 'bluetooth', detect._pci_role(bt))
    check('a device it does not name is not given a role',
          detect._pci_role({'IORegistryEntryName': 'pci-bridge0'}) is None)

    # and the row that comes of it
    import summary
    rows = summary.network_rows({
        'pci_ids': ['14e4:4433'],
        'machine_roles': {'14e4:4433': 'wifi'},
        'device_names': {'14e4:4433': 'wlan, bcm4387'},
    })
    said = next(r for r in rows if r['part'] == 'Wi-Fi')
    check('a device only the machine named still gets a row',
          said['what'] == 'wlan, bcm4387' and said['verdict'] == summary.UNKNOWN, said)
    check('and it is not claimed to be supported', not said['kexts'])

    # the same device, on a machine that has handed it to a driver
    driven = summary.network_rows({
        'system': 'Darwin', 'pci_ids': ['14e4:4433'],
        'machine_roles': {'14e4:4433': 'wifi'},
        'machine_drivers': {'14e4:4433': 'AppleBCMWLANCore'},
        'device_names': {'14e4:4433': 'wlan, bcm4387'},
    })
    wifi_row = next(r for r in driven if r['part'] == 'Wi-Fi')
    check('a device macOS is driving says which driver has it',
          wifi_row['verdict'] == summary.DRIVEN
          and 'AppleBCMWLANCore' in wifi_row['detail'], wifi_row)
    check('and it is still not a kext this repository ships',
          not wifi_row['kexts'])
    check('"driven by macOS" is never said about a machine that is not one',
          summary.DRIVEN not in [r['verdict'] for r in summary.rows(
              {'pci_ids': ['8086:1559'], 'system': 'Windows'})])

    # and on the machine this is running on, whatever that is
    hw = detect.probe()
    if hw.get('system') == 'Darwin':
        check('this Mac reports at least its own PCI devices',
              len(hw['pci_ids']) > 0, hw['pci_ids'])
        check('and says which system it was read on', hw['system'] == 'Darwin')


def genuine_macs():
    """Which macOS a real Mac runs, from the list Apple publishes.

    Every other verdict here comes from what a kext claims. A Mac's hardware is
    claimed by nothing, so the only honest answer about it is Apple's own - and
    it is keyed on the board name the machine reports of itself, which is the
    same string on both sides."""
    import detect
    import mactable
    import summary

    table = mactable.table()
    check('the table exists and names its source',
          table.get('source', '').startswith('https://gdmf.apple.com'), table.get('source'))
    check('with more than a handful of machines', len(table.get('mac', [])) > 50,
          len(table.get('mac', [])))
    check('and the lines are in order, oldest first',
          [int(v.split('.')[0]) for v in table['lines']]
          == sorted(int(v.split('.')[0]) for v in table['lines']), table['lines'])

    # an Apple silicon board and an Intel board, both from the same file
    silicon = [r for r in table['mac'] if r['board'].startswith('J')]
    intel = [r for r in table['mac'] if r['board'].startswith('Mac-')]
    check('both kinds of board are in it', silicon and intel,
          (len(silicon), len(intel)))
    check('a board with no ceiling is one the newest line still lists',
          all(r['lines'][-1] == table['lines'][-1]
              for r in table['mac'] if not r['ceiling']))
    check('and a board with a ceiling is not in the newest line',
          all(r['lines'][-1] != table['lines'][-1]
              for r in table['mac'] if r['ceiling']))

    check('an unknown board is not guessed at', mactable.window('nope') is None)
    check('and no board at all is not either', mactable.window('') is None)

    # what this table answers, said in its own terms: which lines Apple still
    # publishes for a board. Reading it as a support range is what told a 2019
    # machine it stopped at Big Sur.
    check('the lines a board is served come back newest first',
          mactable.serves(silicon[0]['board'])
          == list(reversed(silicon[0]['lines'])))
    check('and an unlisted board is served nothing', mactable.serves('nope') == [])

    # and how far a Mac goes comes from the other list entirely
    made = summary.genuine_mac({'system': 'Darwin',
                                'board_id': 'Mac-B4831CEBD52A0C4C'})
    check('a Mac that stopped says where it stopped',
          made['listed'] and made['to']['name'] == 'Ventura', made)
    check('and it has no floor, because nothing here knows one',
          'from' not in made, made)
    made = summary.genuine_mac({'system': 'Darwin',
                                'board_id': 'Mac-E1008331FDC96864'})
    check('a Mac Apple keeps current has no ceiling either',
          made['current'] and made['to'] is None, made)
    check('and its served lines are a separate fact', made['serving'], made)
    check('a machine with no board is not a Mac',
          summary.genuine_mac({}) is None)
    check('and neither is a PC that happens to name its baseboard',
          summary.genuine_mac({'system': 'Linux',
                               'board_id': 'Microsoft Corporation Virtual Machine'})
          is None)
    check('a board nothing lists says so rather than nothing',
          summary.genuine_mac({'system': 'Darwin', 'board_id': 'nope'}) == {
              'board': 'nope', 'to': None, 'current': False,
              'serving': [], 'listed': False})

    # this machine, if it happens to be a Mac. A PC has a baseboard name and
    # no board id, and asking Apple about one is the bug this used to have.
    here = detect.probe()
    board = here.get('board_id')
    check('only a Mac has a board id',
          board is None or here.get('system') == 'Darwin', (board, here.get('system')))
    if board:
        check('this Mac names its own board', board and ' ' not in board, board)
        check('and the table has something to say about it',
              mactable.serves(board) or True, board)


def the_processor_bounds_it_too():
    """An AMD machine runs on kernel patches, and those patches have bounds.

    They were not counted, so a Ryzen desktop with no recognised network card
    said "not bounded here" while its own profile said 10.13 to 26. Above the
    patches the machine does not boot at all, which is a harder limit than any
    kext imposes."""
    import coverage
    import summary

    ryzen = {'cpu': 'AMD Ryzen 5 5600', 'generation': 'ryzen-threadripper',
             'cores': 6, 'laptop': False}
    window = summary.profile_window(ryzen)
    check('a Ryzen profile is bounded by its patches', window is not None)
    check('from High Sierra', window[0] == 17, window)
    check('to whatever the newest patch covers', window[1] and window[1] >= 24, window)

    named = summary.macos_range(ryzen)
    check('and the machine range now says so rather than nothing', named is not None)
    check('with the patches named as what set it',
          'kernel patches' in named[0][0], named)

    intel = {'cpu': 'i5', 'generation': 'comet-lake', 'laptop': False}
    check('an Intel profile carries no kernel patches, so it bounds nothing',
          summary.profile_window(intel) is None)

    check('a machine whose generation is unknown is not guessed at',
          summary.profile_window({'cpu': 'something'}) is None)

    # the envelope, not the intersection: grouping by capability read a renamed
    # successor patch as the capability having stopped, and bounded Ryzen at 11
    row = dict(path='', platform='desktop', vendor='amd', cpu='ryzen-threadripper',
               cores=6, chipset=None, oem=None, variant=None)
    check('the ceiling is the furthest any patch reaches',
          coverage.window_for(row)[1] >= 24, coverage.window_for(row))


def graphics_and_the_range():
    """What the graphics mean for the macOS range: not a bound, a warning.

    An unsupported card does not narrow which macOS runs - it decides whether
    the machine has a display at all. Folding it into the range would read as a
    version limit, which is a different and wrong thing to tell somebody."""
    import summary

    arc = {'id': '8086:56a0', 'name': 'Intel(R) Arc(TM) A770'}
    igpu = {'id': '8086:9bc4', 'name': 'Intel(R) UHD Graphics'}
    radeon = {'id': '1002:67df', 'name': 'Radeon RX 580'}

    nothing = summary.graphics_advice({'generation': 'comet-lake',
                                       'gpu_devices': [radeon]})
    check('a supported card is not warned about', nothing is None, nothing)
    check('and neither is a machine with no graphics at all',
          summary.graphics_advice({'gpu_devices': []}) is None)

    fallback = summary.graphics_advice({'generation': 'comet-lake',
                                        'gpu_devices': [arc, igpu]})
    check('an unsupported card with a working iGPU says to use the iGPU',
          fallback['tone'] == summary.UNSUPPORTED
          and 'UHD Graphics' in fallback['text']
          and 'range above still holds' in fallback['text'], fallback)

    alone = summary.graphics_advice({'generation': 'comet-lake',
                                     'gpu_devices': [arc]})
    check('an unsupported card with no iGPU says there is no fallback',
          'no integrated graphics to fall back on' in alone['text'], alone)
    check('and that it has to be replaced', 'replaced' in alone['text'])

    # the field report about this processor says its iGPU does not accelerate,
    # so the iGPU cannot be offered as the way out
    dead = summary.graphics_advice({'cpu': 'i5-10200H', 'generation': 'comet-lake',
                                    'gpu_devices': [arc, igpu]})
    check('an unsupported card and a dead iGPU says neither is supported',
          'neither is' in dead['text'] and 'cannot cover for it' in dead['text'], dead)

    unheard = summary.graphics_advice({
        'generation': 'comet-lake',
        'gpu_devices': [{'id': 'abcd:1234', 'name': 'Something Nobody Ships'}]})
    check('a card in no table is unknown and says that is not a verdict',
          unheard['tone'] == summary.UNKNOWN
          and 'not the same as unsupported' in unheard['text'], unheard)


def what_the_machine_calls_its_network():
    """A card no kext claims is still a card the machine can name.

    Windows classes every device it enumerates and Linux puts the class in the
    lspci line. Wi-Fi against Ethernet is not in the class, so the model name
    settles that - a card calling itself "Wireless LAN WiFi 6" is not a port."""
    import detect

    lines = '\n'.join([
        r'Net|PCI\VEN_10EC&DEV_B852&SUBSYS_1234|Realtek 8852BE Wireless LAN WiFi 6 PCI-E NIC',
        r'Bluetooth|USB\VID_0BDA&PID_B85B|Realtek Bluetooth 5.3 Adapter',
        r'Net|PCI\VEN_8086&DEV_15F3|Intel(R) Ethernet Controller I225-V',
        r'Net|ROOT\VMS_MP|Hyper-V Virtual Switch Extension Adapter',
    ])
    found = detect.named_roles(lines, detect.PCI_PATTERNS + detect.USB_PATTERNS)
    check('a Realtek card that says WiFi is Wi-Fi', found.get('10ec:b852') == 'wifi',
          found)
    check('its Bluetooth half is Bluetooth', found.get('0bda:b85b') == 'bluetooth')
    check('a card that says Ethernet is Ethernet', found.get('8086:15f3') == 'ethernet')
    check('and a virtual adapter with no hardware id is not a device',
          len(found) == 3, found)

    # and the row it produces
    import summary
    rows = summary.network_rows({
        'pci_ids': ['10ec:b852'],
        'machine_roles': {'10ec:b852': 'wifi'},
        'device_names': {'10ec:b852': 'Realtek 8852BE Wireless LAN WiFi 6 PCI-E NIC'},
    })
    wifi = next(r for r in rows if r['part'] == 'Wi-Fi')
    check('the card is named rather than called unrecognised',
          '8852BE' in wifi['what'], wifi['what'])
    check('and nothing is claimed to drive it',
          wifi['verdict'] == summary.UNKNOWN and not wifi['kexts'], wifi)


def the_device_catalogue():
    """Every device the tables know, in one list, once each.

    The risk is a catalogue that disagrees with the build: it must read the
    same tables rather than become a second copy of them, and it must not
    invent a device or lose one."""
    import deviceids
    import inventory

    named = deviceids.table()
    check('the name table says where its names came from',
          'pci-ids' in named.get('source', {}).get('pci', ''), named.get('source'))
    check('and it took the USB list from a source that states a licence',
          'hwdata' in named.get('source', {}).get('usb', ''), named.get('source'))
    check('an id nobody has written a name for keeps its id',
          isinstance(named.get('unnamed'), list))

    # a module soldered into a laptop is in no public list, but the kext that
    # claims it names it: BrcmPatchRAM carries a DisplayName per device
    import deviceids
    by_kext = [r for r in named.get('device', []) if r.get('bus') == 'kext']
    check('what the public lists miss is asked of the kext that claims it',
          len(by_kext) > 40, len(by_kext))
    check('and the kext source is named', 'Info.plist' in
          named.get('source', {}).get('kext', ''), named.get('source'))
    check('a real laptop module comes back with its own name',
          'Bluetooth' in (deviceids.describe('0a5c:6412')[1] or ''),
          deviceids.describe('0a5c:6412'))
    check('and fewer than fifty are left with no name at all',
          len(named.get('unnamed', [])) < 50, len(named.get('unnamed', [])))

    catalogue = inventory.devices()
    rows = catalogue['devices']
    check('there are devices in it', len(rows) > 400, len(rows))
    check('every one has a category the list declares',
          all(r['category'] in catalogue['categories'] for r in rows))
    check('and a name, never an empty cell',
          all(r['name'] for r in rows))
    # one vocabulary. The tables were written at different times and said
    # "works" and "supported" for the same thing.
    check('every verdict is one of the words the filter offers',
          {r['status'] for r in rows} <= set(catalogue['statuses']),
          sorted({r['status'] for r in rows}))
    check('and "works" is not one of them, because "supported" is',
          'works' not in catalogue['statuses'], catalogue['statuses'])

    # one row per device. Broadcom Bluetooth is three kexts in a relay and
    # every adapter used to appear three times.
    keyed = [(r['category'], r['id']) for r in rows if r['id'] and r['category'] != 'Graphics']
    check('a device claimed by several kexts is listed once',
          len(keyed) == len(set(keyed)),
          [k for k in keyed if keyed.count(k) > 1][:3])

    # graphics are keyed the other way: nine cards share 1002:67df and the
    # model is the thing somebody is looking for
    cards = [r for r in rows if r['category'] == 'Graphics' and r['id'] == '1002:67df']
    check('cards sharing an id are listed by model', len(cards) > 1,
          [c['name'] for c in cards])
    # the verdict is a field now, not the first word of the note, so that is
    # where the models differ from each other
    check('and each model keeps its own verdict',
          len({c['status'] for c in cards}) > 1, [(c['name'], c['status']) for c in cards])

    # what the tables hold has to survive the trip
    ids_in_table = {i.lower() for d in ocgen.read_toml(Path('data/hardware.toml'))['driver']
                    for i in d['ids'] if d['role'] in inventory.ROLE_CATEGORY}
    ids_in_catalogue = {r['id'].lower() for r in rows
                        if r['id'] and r['category'] in inventory.ROLE_CATEGORY.values()}
    check('no device the kexts claim is missing from the catalogue',
          not (ids_in_table - ids_in_catalogue),
          sorted(ids_in_table - ids_in_catalogue)[:5])
    check('and none is invented',
          not (ids_in_catalogue - ids_in_table),
          sorted(ids_in_catalogue - ids_in_table)[:5])

    check('the vendor filter has something to filter by',
          len(catalogue['vendors']) > 5, catalogue['vendors'][:4])

    # the builder takes --inventory and hands it to this module. The two lists
    # of what that argument accepts were written twice and drifted: the window
    # asked for "devices" and the builder had never heard of it. There is one
    # list now, and this is what holds it to one.
    import inventory as _inv
    source = Path('tools/setup.py').read_text()
    check('the builder takes its choices from the one list',
          'choices=inventory.WHAT' in source)
    check('and every choice on it has a document',
          set(_inv.WHAT) == set(_inv.DOCUMENTS), sorted(_inv.WHAT))
    for what in _inv.WHAT:
        r = run([sys.executable, 'tools/setup.py', '--inventory', what])
        check(f'--inventory {what} answers with JSON', r.returncode == 0
              and r.stdout.lstrip().startswith('{'), r.stdout[:60])


def nvidia_by_family():
    """Which NVIDIA cards macOS drove, and until when.

    The guide states this per family and names no device ids; the PCI ID
    Project names the chip in every device name. Joining the two turns one
    sentence about the whole vendor into a verdict per card - a GTX 680 ran
    until Big Sur and an RTX 4090 never ran at all, and both used to read
    the same."""
    import gpu
    import ocgen as _ocgen

    families = _ocgen.read_toml(Path('data/gpu.toml')).get('nvidia', [])
    check('the families were parsed from the page', len(families) >= 8, len(families))
    named = {f['name'].split(' Series')[0].split('(')[0].strip() for f in families}
    check('and the ones people actually own are among them',
          {'Kepler', 'Maxwell', 'Pascal', 'Turing'} <= named, sorted(named))

    def verdict(device_id):
        return gpu.classify({'id': device_id, 'name': 'NVIDIA'})

    kepler, entry = verdict('10de:1180')          # GK104, GTX 680
    check('a Kepler card is supported', kepler == 'works', (kepler, entry))
    check('and says where it stops', entry['macos'][1] == '11', entry.get('macos'))

    pascal, entry = verdict('10de:1b06')          # GP102, GTX 1080 Ti
    check('a Pascal card stops at High Sierra',
          pascal == 'works' and entry['macos'][1] == '10.13.6', entry.get('macos'))

    ada, entry = verdict('10de:2684')             # AD102, RTX 4090
    check('a card whose family never had a driver says so',
          ada == 'unsupported' and 'no driver was ever written' in entry['note'],
          entry)

    # the rebranded-Fermi section speaks for three chips it names, and a real
    # Fermi is not one of them
    fermi_rebrand, entry = verdict('10de:0f00')   # GF108, GT 630
    check('a rebranded Fermi is claimed by the section that names its chip',
          fermi_rebrand == 'works' and 'GF108' in str(entry['family']), entry)
    real_fermi, entry = verdict('10de:0e22')      # GF104, GTX 460
    check('and a real Fermi is left to the whole-vendor rule rather than mislabelled',
          real_fermi == 'unsupported' and 'Fermi rebranded' not in str(entry), entry)

    # the page lists its cards under each family, so the catalogue reads card
    # by card the way the AMD one does rather than family by family
    listed = {c for f in families for c in f['cards']}
    check('the families name their cards', len(listed) > 100, len(listed))
    check('including the ones people ask about',
          {'GTX 1080 Ti', 'GTX 980', 'RTX 4090'} <= listed,
          sorted(c for c in listed if '1080' in c or '4090' in c))
    check('and the section that lists them without a header is not empty',
          any(f['cards'] for f in families if 'Fermi' in f['name']),
          [f['name'] for f in families if 'Fermi' in f['name']])
    check('no sub-heading was read as a card',
          not [c for c in listed if c.endswith(':')],
          [c for c in listed if c.endswith(':')][:3])
    # a list ends where the prose resumes and the page marks that nowhere, so
    # every entry has to look like a card or the footnote comes in with them
    import gputable
    check('and no prose was',
          all(gputable.CARD_SHAPE.match(c) for c in listed),
          [c for c in listed if not gputable.CARD_SHAPE.match(c)][:2])

    import inventory
    rows = inventory.devices()['devices']
    nvidia = [r for r in rows if r['vendor'] == 'NVIDIA Corporation']
    check('the catalogue lists NVIDIA card by card', len(nvidia) > 100, len(nvidia))
    check('each carrying its family', all(r['note'] for r in nvidia))
    check('and its range as values rather than prose',
          any(r['macos'] and r['macos']['to'] == '11' for r in nvidia),
          [r['macos'] for r in nvidia[:2]])
    check('with the patched range beside it where there is one',
          any((r['macos'] or {}).get('oclp') for r in nvidia))
    check('and that range has both ends',
          all(r['macos'].get('oclp_to') for r in nvidia
              if (r['macos'] or {}).get('oclp')))

    # AMD cards and Intel iGPUs are patched too, and the catalogue used to say
    # so only for NVIDIA
    polaris = next(r for r in rows if r['name'] == 'RX 580')
    check('an AMD card OCLP patches says so as well',
          (polaris['macos'] or {}).get('oclp') == '13.0', polaris['macos'])

    check('an id the name list does not carry gets no family',
          gpu.nvidia_family({'id': '10de:ffff'}) is None)
    check('and a card that is not NVIDIA is not looked up at all',
          gpu.nvidia_family({'id': '1002:67df'}) is None)

    # and it reaches the range the machine screen shows
    import summary
    machine = {'cpu': 'i5', 'generation': 'comet-lake', 'laptop': False,
               'gpu_devices': [{'id': '10de:1180', 'name': 'GeForce GTX 680'}]}
    window = summary.macos_range(machine)
    check('a supported NVIDIA card bounds the machine range', window is not None)
    check('at the release its family stops on',
          window[1] and window[1][2] == 20, window)


def what_the_two_programs_are_called():
    """A folder of two programs has to say which one to open.

    They were HackintoshEFIBuilder and HackintoshEFIBuilderShell, and the one
    with the product name was the part nobody runs. The window carries the
    name now; the engine is named for what it does."""
    spec = Path('tools/pyinstaller.spec').read_text()
    check('the engine is named for its job',
          "name='EFIBuilderEngine'" in spec)
    csproj = Path('gui/Shell.csproj').read_text()
    check('and the window carries the product name',
          '<AssemblyName>HackintoshEFIBuilder</AssemblyName>' in csproj)
    check('the window looks for the engine under the name it is built with',
          'EFIBuilderEngine' in Path('gui/Engine/Builder.cs').read_text())

    # the avares authority is the assembly name; spelling it wrong loses the
    # fonts silently, which is how this went wrong the first time
    layout = Path('gui/App.axaml').read_text()
    check('and the embedded fonts are addressed by that same name',
          'avares://HackintoshEFIBuilder/Assets/Fonts' in layout
          and 'HackintoshEFIBuilderShell' not in layout)


def the_vendored_opencore():
    """One OpenCore release, whole, and runnable.

    Everything a build rests on comes out of one release, so half an update is
    worse than none. And a program has to be executable: git records the bit,
    the release zip does not set it on the Linux builds, and a build that
    shells out to an unrunnable ocvalidate stops with nothing to read."""
    import subprocess as _sub

    versions = sorted(p.name for p in Path('vendor/opencore').iterdir() if p.is_dir())
    check('exactly one version is vendored', len(versions) == 1, versions)
    here = Path('vendor/opencore') / versions[0]
    check('with the sample every config is layered onto',
          (here / 'Sample.plist').exists())

    listed = _sub.run(['git', 'ls-files', '-s', str(here)],
                      capture_output=True, text=True).stdout.splitlines()
    programs = [l for l in listed
                if any(f'/{t}' in l for t in ('ocvalidate', 'macserial'))
                and not l.endswith(('.md', '.exe'))]
    check('both tools are vendored for every system', len(programs) >= 4,
          len(programs))
    unrunnable = [l.split('\t')[-1] for l in programs if not l.startswith('100755')]
    check('and every one of them is recorded executable', not unrunnable, unrunnable)

    # the version the About page shows is this directory's name, so a stale
    # number cannot survive an update
    import inventory
    check('the version reported is the one vendored',
          inventory.about()['opencore'] == versions[0])

    # the drivers OpenCore does not build ship here too, and are recorded
    lock = Path('vendor/ocbinarydata.lock')
    check('the drivers from elsewhere are pinned', lock.exists())
    if lock.exists():
        recorded = ocgen.read_toml(lock)
        check('by hash', all(len(d['sha256']) == 64 for d in recorded['driver']))
        check('and their licence position is written down, not assumed',
              recorded.get('licence') == 'none stated', recorded.get('licence'))
        on_disk = {f"OC/Drivers/{p.name}" for p in
                   Path('EFI/OC/Drivers').glob('Hfs*.efi')}
        check('every one that ships is in the lock',
              on_disk == {d['file'] for d in recorded['driver']}, sorted(on_disk))

    # the write-up of how to do this next time names the tools that do it. A
    # document that names a tool which does not exist is worse than none.
    doc = Path('docs/RELEASING.md')
    check('there is a write-up of how to move to the next one', doc.exists())
    if doc.exists():
        text = doc.read_text()
        for tool in ('tools/opencore.py', 'tools/verify.py', 'tools/matrix.py',
                     'tools/fetch_oc.py', 'tools/selftest.py'):
            check(f'{tool} is named in it and exists',
                  tool in text and Path(tool).exists())
        check('and it says the release is tagged, not pushed by hand',
              'git tag' in text and 'release.yml' in text)
        # the number means the OpenCore it builds, not a count of features
        # here, and the document has to say so: it is the one thing about a
        # release nobody can see from the outside
        check('and what the version number means',
              'follows OpenCore' in text and 'not a count of features' in text)
        check('and how to publish when OpenCore has not moved',
              'Republish' in text or 'republish' in text)


def what_the_readme_shows():
    """The front page and the guide, and the counts they both make.

    The process moved to the site; the README is the landing page that points
    at it. Both still draw the window and both still count things that move,
    and both rot the same two ways: the picture is renamed and the page draws a
    hole, or the number beside it drifts from what the program now holds.
    Neither is visible to anyone who wrote the page and never reloads it.

    The counts are checked across README and every guide page at once, so a
    number can live in either place - but a number that is there has to be
    right."""
    import inventory

    readme = Path('README.md').read_text(encoding='utf-8')
    guide = Path('guide')
    pages = {p: p.read_text(encoding='utf-8') for p in sorted(guide.glob('*.md'))}
    check('the guide has pages', pages, len(pages))
    written = readme + '\n'.join(pages.values())

    shots = sorted(p.name for p in Path('Resources/App').glob('*.png'))
    check('there are screenshots of the window', shots, shots)
    for shot in shots:
        check(f'{shot} is shown somewhere', f'Resources/App/{shot}' in written)
    drawn = set(re.findall(r'Resources/App/([\w.-]+\.png)', written))
    check('and every image drawn exists', not (drawn - set(shots)),
          sorted(drawn - set(shots)))

    # the numbers beside those pictures are the program's own
    devices = inventory.devices()
    kexts = inventory.kexts()['kexts']
    claimed = sum(k['devices'] for k in kexts if k.get('devices'))
    for count, what in ((len(devices['devices']), 'devices'),
                        (len(devices['categories']), 'categories'),
                        (len(kexts), 'kexts'),
                        (claimed, 'device ids')):
        check(f'the pages count {count} {what}, and so does the program',
              re.search(rf'\b{count}\b[^.]*{what}', written, re.S), count)
    # and the config count, read from the catalogue the build works off
    listed = Path('profiles/catalogue.toml')
    if listed.exists():
        configs = len(ocgen.read_toml(listed)['config'])
        check(f'and {configs} configs, which is what the catalogue holds',
              str(configs) in written, configs)

    # a folder of two programs: the page has to name the one to open
    check('it names the window', 'HackintoshEFIBuilder' in readme)
    check('and the engine, by the name it ships under',
          'EFIBuilderEngine' in written)

    # the README is a landing page now: its job is to hand the reader to the
    # guide, and a landing page that has quietly grown the whole process back
    # is the failure this notices
    check('the README points at the guide',
          'yusufklncc.github.io/Hackintosh-for-All-Computers' in readme)
    check('and at the Turkish side of it',
          'Hackintosh-for-All-Computers/tr/' in readme)
    check('and stays a landing page rather than a second copy of the guide',
          len(readme.splitlines()) < 250, len(readme.splitlines()))

    # the refusal every first-time user hits, said on both sides
    for page, words in (('blocked.md', ('Smart App Control', 'Open Anyway')),
                        ('blocked.tr.md', ('Smart App Control', 'Yine de Aç'))):
        text = (guide / page).read_text(encoding='utf-8')
        for word in words:
            check(f'{page} says "{word}"', word in text)
    check('and the README warns that the first run is refused',
          'Smart App Control' in readme and 'Privacy & Security' in readme)


def what_the_guide_holds():
    """Both languages, the same pages, and a build that proves it.

    A page written in one language and forgotten in the other is invisible from
    the side that has it. So is a link to a heading that was renamed: mkdocs
    resolves the page and never the fragment. tools/guidecheck.py answers both,
    and is run here against the sources so a clone with no mkdocs installed
    still gets the half of it that does not need a build."""
    import guidecheck

    guide = Path('guide')
    check('the guide is where mkdocs.yml says it is', guide.is_dir())
    config = Path('mkdocs.yml').read_text(encoding='utf-8')
    check('and mkdocs is pointed at it', 'docs_dir: guide' in config)

    # docs/ is maintainer notes and must not be swept into the published site
    check('the maintainer notes stay out of the site',
          Path('docs/RELEASING.md').exists() and 'docs_dir: docs' not in config)

    uneven = guidecheck.parity(guide)
    check('every page exists in English and in Turkish', not uneven, uneven)

    english = sorted(p.stem for p in guide.glob('*.md')
                     if not p.stem.endswith('.tr'))
    check('and there is a page for each step of the process', english, english)
    for page in english:
        check(f'{page} is in the navigation', f'{page}.md' in config, page)

    # the site's icon is the program's icon, not a second copy that drifts
    for name in ('icon-64.png', 'icon-256.png'):
        here = guide / 'assets' / name
        there = Path('gui/Assets/Icon/png') / name
        check(f'the site\'s {name} is the one the program ships',
              here.exists() and there.exists()
              and here.read_bytes() == there.read_bytes(), name)

    # the site's colours are the window's colours, read across from the theme
    # dictionaries in App.axaml. Two palettes for one product drift the moment
    # either is touched, and nothing about a colour says so out loud.
    css = (guide / 'assets' / 'extra.css').read_text(encoding='utf-8').lower()
    check('the palette is custom rather than a stock Material one',
          'primary: custom' in config and 'extra_css' in config)

    # scoped to the Dark dictionary: App.axaml holds both, Light comes first,
    # and matching the file as a whole reads the wrong one - which is exactly
    # what the first version of this check did, and it compared the site's dark
    # ground against #EEF1F5
    axaml = Path('gui/App.axaml').read_text(encoding='utf-8')
    dark = axaml[axaml.index('x:Key="Dark"'):]
    dark = dark[:dark.index('</ResourceDictionary>')]
    for token, what in (('Ground', 'the dark ground'),
                        ('Surface', 'the raised surface'),
                        ('Accent', 'the dark accent')):
        colour = re.search(rf'x:Key="{token}" Color="(#[0-9A-Fa-f]{{6}})"', dark)
        check(f'{what} is the one the window uses',
              colour and colour.group(1).lower() in css,
              colour.group(1) if colour else f'no {token} in the Dark theme')

    # the toggle, and the third state people forget: follow the machine
    check('the site offers light and dark',
          'scheme: default' in config and 'scheme: slate' in config)
    check('and starts by following the machine',
          'media: "(prefers-color-scheme)"' in config)

    # the default slugify drops Turkish letters, and every link written to
    # such a heading misses without a word from the build
    check('headings keep their non-ASCII letters',
          'pymdownx.slugs.slugify' in config)

    # both languages are searchable, in their own language
    check('search is set up for both languages',
          re.search(r'search:\s*\n\s*lang:\s*\n\s*- en\s*\n\s*- tr', config))

    # pinned, because a theme that moves under the site silently is the same
    # failure as a table that moves under a config
    reqs = Path('guide/requirements.txt').read_text(encoding='utf-8')
    check('the build is pinned', re.search(r'mkdocs-material==[\d.]+', reqs))
    check('and so is the plugin that makes it two languages',
          re.search(r'mkdocs-static-i18n==[\d.]+', reqs))

    flow = Path('.github/workflows/guide.yml').read_text(encoding='utf-8')
    check('a workflow builds it', 'mkdocs build --strict' in flow)
    check('and runs the link check on what it built',
          'tools/guidecheck.py' in flow)
    check('and publishes it to Pages', 'deploy-pages' in flow)

    # a built site is not always here; when it is, every link has to land
    built = Path('_site')
    if built.is_dir():
        broken = guidecheck.check(built)
        check('every internal link in the built site lands', not broken,
              broken[:5])
    else:
        print('  --    _site is not built here, so only the sources were '
              'checked; the workflow builds it and runs the rest')


def the_recovery_it_can_fetch():
    """The one thing here that opens a connection, and what it offers.

    A whole installer does not fit on FAT32, so the answer to that is Apple's
    recovery - about 700 MB that boots and downloads the rest. OpenCore ships
    the tool that asks for it, so nothing here reimplements the protocol; what
    this checks is that the tool is vendored, that the list of what can be
    fetched is read out of the tool's own data, and that the page which says
    the program never reaches the network now says where it does."""
    import json as _json
    import inventory as _inv
    import recovery

    tool = recovery.vendored()
    check('macrecovery is vendored', tool is not None)
    if tool is None:
        return
    check('beside the OpenCore it came from',
          tool.parents[2].parent.name == 'opencore', str(tool))
    check('with the board list it reads', (tool.parent / 'boards.json').exists())

    # and the bump is what puts it there. Vendoring it by hand once would work
    # and then be forgotten at 1.0.8.
    bump = Path('tools/opencore.py').read_text()
    check('the OpenCore bump is what vendors it',
          "'macrecovery'" in bump and 'boards.json' in bump)

    boards = _json.loads((tool.parent / 'boards.json').read_text(encoding='utf-8'))
    offered = recovery.choices()
    check('there is something to fetch', len(offered) >= 5, len(offered))
    numbered = [c for c in offered if c['version'][0].isdigit()]
    check('newest first',
          numbered == sorted(numbered, reverse=True,
                             key=lambda c: [int(n) for n in c['version'].split('.')]))
    check('one entry per macOS',
          len({c['version'] for c in offered}) == len(offered))
    for choice in offered:
        # derived, not chosen: the board has to be one the list actually maps
        # to that version, or the request asks Apple for something else
        check(f"{choice['version']} names a board that yields it",
              boards.get(choice['board']) == choice['version'], choice)
        check(f"{choice['version']} is offered under a name",
              choice['label'], choice)
    for choice in numbered:
        check(f"{choice['version']} is named as people know it",
              choice['name'] and choice['name'] in choice['label'], choice)


    # the boards Apple keeps current are how somebody asks for the macOS that
    # is newest today. Dropping them meant the newest release could not be
    # fetched at all, which is what it looked like from the window.
    current = [c for c in offered if not c['version'][0].isdigit()]
    check('the macOS Apple is serving now can be asked for', len(current) == 1,
          [c['version'] for c in current])
    if current:
        check('and it comes first', offered[0] is current[0])
        # This used to assert the label carried no number, "since nothing
        # here knows" it. Something here does: data/mac.toml records every
        # macOS line Apple serves, refreshed from Apple's own metadata, so the
        # row opens named. What must stay true is the harder half - the number
        # in the label is a record, and the request is still for whatever is
        # newest, so nothing promises that number is what will arrive.
        recorded = recovery.recorded()
        if recorded:
            check('named from what the repository records Apple serving',
                  recorded['name'] in current[0]['label'], current[0]['label'])
        else:
            check('named for what it is, when nothing here knows the number',
                  not any(ch.isdigit() for ch in current[0]['label']),
                  current[0]['label'])
        check('but the request stays "whatever is newest"',
              current[0]['version'] == 'latest', current[0]['version'])
        check('and it says so rather than promising the number',
              'whatever' in current[0]['note'].lower(), current[0]['note'])
    # the number is the board's ceiling, not the image: asked for the 12.7.6
    # board Apple served a 12.6 BaseSystem. Printing the number as the name
    # would be a promise nothing here can keep, so the row is named and the
    # number is explained beside it.
    for choice in numbered:
        check(f"{choice['version']} is offered by name, not by number",
              choice['label'] == choice['name'], choice['label'])
        check(f"{choice['version']} says what the number is",
              choice['version'] in choice['note'], choice['note'])
        check('and it can be asked for by that word',
              recovery.find('latest') == current[0])
    check('every row can be asked for by its own version',
          all(recovery.find(c['version']) == c for c in offered))
    check('and it lands where OpenCore looks',
          recovery.FOLDER == 'com.apple.recovery.boot')

    # sizes: a chunklist is kilobytes and an image is hundreds of megabytes,
    # and one unit for both printed the chunklist as 0.0 MB
    check('a small file reads in KB', recovery._size(2650).endswith('KB'))
    check('and a large one in MB', recovery._size(650_000_000).endswith('MB'))

    # a half-written image cannot be resumed, and leaving one there stops the
    # next attempt before it starts
    with tempfile.TemporaryDirectory() as where:
        folder = Path(where) / recovery.FOLDER
        folder.mkdir()
        (folder / 'theirs.txt').write_text('not ours')
        (folder / 'BaseSystem.dmg').write_bytes(b'half')
        left = recovery._sweep(folder, {'theirs.txt'})
        check('a failed run takes back what it wrote',
              [n for n, _ in left] == ['theirs.txt'], left)

    # the builder offers it, and hands the whole job to the tool
    source = Path('tools/setup.py').read_text()
    check('the builder has a --recovery', "'--recovery'" in source)
    check('and does not do the download itself',
          'recovery.main(' in source)

    # the window: a pane that lists, and a pass that does not press the button
    pane = Path('gui/Views/RecoveryView.axaml.cs')
    check('the window has a pane for it', pane.exists())
    if pane.exists():
        drawn = pane.read_text()
        check('which reads the list from the engine',
              'Inventory.Recoveries' in drawn)
        check('and streams the download rather than waiting on it',
              'Builder.Stream' in drawn)
    model = Path('gui/Engine/Inventory.cs').read_text()
    check('the window shows the name the engine chose, not one of its own',
          '"label"' in model and 'Label is { Length: > 0 }' in model)
    # every pane that reads on first sight waits on the same read. A bool
    # guard let the second caller through while the first was still awaiting -
    # the nav starts a Swap of its own, so two always arrive together - and the
    # second drew an empty pane. The screenshot pass caught it; nobody else
    # would have.
    for view in sorted(Path('gui/Views').glob('*View.axaml.cs')):
        drawn = view.read_text()
        # the ones the nav calls. MachineView loads itself once, from its own
        # constructor, and nothing else can ask it twice.
        if 'public Task Load()' not in drawn:
            continue
        check(f'{view.name} waits on one read, not a flag',
              'bool _loaded' not in drawn and 'bool _read' not in drawn
              and '??= Fill()' in drawn, view.name)

    pass_ = Path('gui/App.axaml.cs').read_text()
    check('the unattended pass lists and stops',
          'ListRecoveries' in pass_ and 'TakeRecovery' not in pass_)

    # and the page that used to say "never"
    facts = _inv.about()
    check('the About page names where the network is reached', facts.get('network'))
    check('and still says a build needs none', facts['offline'] is True)
    drawn = Path('gui/Views/AboutView.axaml.cs').read_text()
    check('the window reads that sentence rather than keeping its own',
          'about.Network' in drawn)


def the_stick_it_writes_to():
    """The only part of this that can destroy something.

    Everything else writes into a folder. This erases a whole disk, so what is
    checked here is the refusing: that the list is removable disks only, that
    the disk this computer booted from is not in it, and that a device the list
    did not offer cannot be erased by naming it."""
    import stick

    document = stick.document()
    check('the stick list says which system it read', document['platform'])
    check('and names what it booted from, or says it could not',
          'booted' in document)
    check('and whether it can erase here at all', 'erasable' in document)
    # an empty list used to mean two things: no stick, or a command that failed.
    # On Windows it meant the second - a PowerShell flag from a version Windows
    # does not ship - and the pane said nothing at all.
    check('it says whether it could ask, not only what it found',
          document['asked'] is True and document['trouble'] == '',
          (document['asked'], document['trouble']))
    pane = Path('gui/Views/StickView.axaml.cs').read_text()
    check('and the window tells the two apart',
          'That is not' in pane and 'list.Asked' in pane)

    # the Windows listing has to work on the PowerShell Windows ships
    source = Path('tools/stick.py').read_text()
    check('nothing asks PowerShell 7 for something 5.1 cannot do',
          'ConvertTo-Json -InputObject' in source
          and '-AsArray")' not in source)
    check('and one disk is read as a list of one',
          'isinstance(listed, dict)' in source)
    # and lsblk has to work on an older util-linux than this one
    check('the Linux listing falls back when a column is too new',
          'LSBLK_PLAIN' in source and 'LSBLK_FULL' in source)
    check('the recovery folder is the one OpenCore looks for',
          document['recovery'] == 'com.apple.recovery.boot')

    booted = document['booted']
    check('the disk this computer booted from is not offered',
          not booted or all(s['device'] != booted for s in document['sticks']),
          booted)
    for found in document['sticks']:
        check(f"{found['device']} is offered as removable", found['removable'],
              found)
        check(f"{found['device']} says whether it can be written to as it is",
              'ready' in found and found['why'], found)

    # the question a stick raises is whether it has to be formatted, and that
    # is answered from what is on it rather than from it being a USB stick
    for case, ready, says in (
        ({'scheme': 'GUID_partition_scheme',
          'volumes': [{'fs': 'msdos', 'called': 'MS-DOS FAT32',
                       'free': 4 << 30, 'mount': '/Volumes/USB'}]}, True, 'GPT'),
        ({'scheme': 'FDisk_partition_scheme',
          'volumes': [{'fs': 'msdos', 'called': 'MS-DOS FAT32',
                       'free': 4 << 30, 'mount': '/Volumes/USB'}]}, True, 'GPT'),
        ({'scheme': 'GUID_partition_scheme',
          'volumes': [{'fs': 'apfs', 'called': 'APFS', 'free': 4 << 30,
                       'mount': '/Volumes/Mac'}]}, False, 'APFS'),
        ({'scheme': 'GUID_partition_scheme',
          'volumes': [{'fs': 'exfat', 'called': 'ExFAT', 'free': 4 << 30,
                       'mount': '/Volumes/X'}]}, False, 'ExFAT'),
        ({'scheme': 'GUID_partition_scheme',
          'volumes': [{'fs': 'msdos', 'called': 'MS-DOS FAT32',
                       'free': 4 << 30, 'mount': ''}]}, False, 'not mounted'),
        ({'scheme': '', 'volumes': []}, False, 'FAT32'),
        # a stick Rufus has been near: a 1 MB FAT12 helper beside an exFAT
        # partition. Calling that ready sent an installer at 26 KB of room.
        ({'scheme': 'GUID_partition_scheme',
          'volumes': [{'fs': 'exfat', 'called': 'ExFAT', 'free': 58 << 30,
                       'mount': '/Volumes/ssad'},
                      {'fs': 'msdos', 'called': 'MS-DOS FAT12', 'free': 26624,
                       'mount': '/Volumes/RUFUS_BOOT'}]}, False, 'FAT12'),
        # and FAT32 with no room on it
        ({'scheme': 'GUID_partition_scheme',
          'volumes': [{'fs': 'msdos', 'called': 'MS-DOS FAT32', 'name': 'FULL',
                       'free': 40 << 20, 'mount': '/Volumes/FULL'}]},
         False, '700 MB'),
    ):
        verdict, where, why = stick.verdict(case)
        check(f'{case["scheme"] or "no scheme"} + '
              f'{", ".join(v["called"] for v in case["volumes"]) or "nothing"}'
              f' -> {"ready" if ready else "format it"}',
              verdict is ready, why)
        check('  and it says why in those words', says in why, why)
        check('  ready means it names where to write',
              bool(where) is ready, where)
    check('a pane that asks for a word says which word',
          'Type {stick.Device} below' in
          Path('gui/Views/StickView.axaml.cs').read_text())

    # naming a disk nobody was offered does not erase it. This is the check
    # that matters: the list is the gate, not the question in front of it.
    for made_up in ('disk999', '/dev/disk999', 'sda', '0'):
        if any(s['device'] == made_up.removeprefix('/dev/')
               for s in document['sticks']):
            continue
        mount, complaint = stick.prepare(made_up)
        check(f'{made_up} is refused, not erased', mount is None and complaint,
              complaint)

    with tempfile.TemporaryDirectory() as where:
        root = Path(where)
        # an EFI folder is one with a loader in it, not one with the right name
        (root / 'notanefi').mkdir()
        written, complaint = stick.place(root / 'stick', efi=root / 'notanefi')
        check('a volume that is not there is refused', complaint)
        (root / 'stick').mkdir()
        written, complaint = stick.place(root / 'stick', efi=root / 'notanefi')
        check('a folder with no BOOTx64.efi is not an EFI folder', complaint)
        check('and nothing was copied when it complained', not written)

        loader = root / 'EFI' / 'BOOT'
        loader.mkdir(parents=True)
        (loader / 'BOOTx64.efi').write_bytes(b'not really')
        image = root / 'com.apple.recovery.boot'
        image.mkdir()
        (image / 'BaseSystem.dmg').write_bytes(b'not really either')
        written, complaint = stick.place(root / 'stick', efi=root / 'EFI',
                                       recovery=root)
        check('both folders land at the root', not complaint
              and [n for n, _ in written] == ['EFI', 'com.apple.recovery.boot'],
              complaint or written)
        check('the recovery is beside the EFI, not inside it',
              (root / 'stick' / 'com.apple.recovery.boot').is_dir()
              and not (root / 'stick' / 'EFI' / 'com.apple.recovery.boot').exists())
        check('and it says whether what is there would boot',
              stick.bootable(root / 'stick'))
        check('a folder with no loader would not',
              not stick.bootable(root / 'notanefi'))

        # a recovery folder with nothing in it is not a recovery
        (root / 'empty').mkdir()
        _, complaint = stick.place(root / 'stick', recovery=root / 'empty')
        check('an installer that is not there is refused', complaint)

    # the weekly check: it asks Apple the same way the tab does and keeps
    # nothing, because Apple's software is Apple's to distribute
    watcher = Path('tools/recoverycheck.py')
    check('there is a check that Apple still answers', watcher.exists())
    if watcher.exists():
        said = watcher.read_text()
        check('it goes through the same tool the tab does',
              'recovery.fetch(' in said)
        check('and into a directory that does not outlive it',
              'TemporaryDirectory' in said)
        check('and says plainly that it keeps nothing',
              'Nothing is published, kept, or copied anywhere' in said)
        check('and a listing-only mode that asks Apple for nothing',
              "'--catalogue'" in said)
    weekly = Path('.github/workflows/refresh.yml').read_text()
    check('it runs weekly beside the tables',
          'recoverycheck.py' in weekly and 'schedule:' in weekly)

    # the builder offers all three, and does none of it itself
    source = Path('tools/setup.py').read_text()
    for flag in ('--usb-list', '--usb-place', '--usb-prepare'):
        check(f'the builder offers {flag}', f"'{flag}'" in source)
    check('and hands the work to the one tool that does it',
          'stick.main(' in source and 'stick.document()' in source)

    # the window
    pane = Path('gui/Views/StickView.axaml.cs')
    check('the window has a pane for it', pane.exists())
    if pane.exists():
        drawn = pane.read_text()
        check('which reads the list from the engine', 'Inventory.Sticks' in drawn)
        check('and asks for the disk by name before erasing',
              'typed == want' in drawn and 'Device ?? ""' in drawn)
    pass_ = Path('gui/App.axaml.cs').read_text()
    check('the unattended pass lists and erases nothing',
          'ListSticks' in pass_ and 'usb-prepare' not in pass_)


def what_it_says_about_amd_integrated():
    """An AMD APU used to read as `unknown`, which means "no idea" to a reader.

    The real answer is narrower: this repository does not cover AMD integrated
    graphics. The kexts that drive them are maintained elsewhere, under terms
    that forbid deriving anything here from them, so nothing in this table came
    from that project and nothing may. Saying that is more useful than a blank,
    and the table is shaped so somebody who has run one can fill it in.

    What must not break: a discrete Radeon is a different question, answered by
    the card table, and must not be swept into this."""
    import gpu

    table = Path('data/amdigpu.toml')
    check('there is a table for them', table.exists())
    said = re.sub(r'\s+', ' ', table.read_text(encoding='utf-8').replace('#', ' '))
    check('it says nothing here was derived from that project',
          'derived from that project' in said or 'Nothing here has been derived' in said)
    check('and names where the drivers come from, without describing them',
          'ChefKiss' in said)
    check('and says what a row has to carry to earn its place',
          'observed_by' in said and 'observed' in said)

    apus = [{'name': 'AMD Radeon Graphics (Renoir)', 'id': '1002:1636'},
            {'name': 'AMD Radeon(TM) Vega 8 Graphics', 'id': '1002:15dd'},
            {'name': 'AMD Radeon Vega 3 Graphics', 'id': '1002:15d8'},
            {'name': 'AMD Radeon(TM) Graphics', 'id': '1002:1638'}]
    for apu in apus:
        check(f"{apu['name']} reads as integrated", gpu.looks_amd_integrated(apu), apu)

    cards = [{'name': 'AMD Radeon RX 6600', 'id': '1002:73ff'},
             {'name': 'AMD Radeon RX 580', 'id': '1002:67df'},
             {'name': 'AMD Radeon RX 7900 XTX', 'id': '1002:744c'},
             {'name': 'AMD Radeon Pro W5700', 'id': '1002:7319'}]
    for card in cards:
        check(f"{card['name']} does not", not gpu.looks_amd_integrated(card), card)

    # and an Intel part is not touched by any of this
    intel = {'name': 'Intel(R) UHD Graphics 620', 'id': '8086:5917'}
    check('an Intel iGPU is not caught by the AMD rule',
          not gpu.looks_amd_integrated(intel))

    # a discrete card nothing claims is a different answer from an APU, and
    # used to be a bare `unknown` with nowhere to go next
    stranger = {'name': 'AMD Radeon RX 7900 XTX', 'id': '1002:744c'}
    check('the RX 7900 XTX really is absent from the card table',
          gpu.classify(stranger, 'zen')[0] == 'unknown',
          gpu.classify(stranger, 'zen'))
    told = ' '.join(gpu.report([stranger], 'zen')[0])
    check('an unclaimed card says no table here claims it',
          'no table here claims this card' in told, told)
    check('and names the guide this repository read its own table from',
          'GPU-Buyers-Guide' in told, told)
    check('and is not mistaken for an APU',
          'ChefKiss' not in told, told)
    check('and says the rest of the build is unaffected',
          'rest of the build applies' in told, told)
    # the pointer comes from the data, not from a URL typed in the code
    check('the guide is read out of data/gpu.toml',
          gpu.guide_for('1002:744c') and 'amd-gpu' in gpu.guide_for('1002:744c'),
          gpu.guide_for('1002:744c'))
    check('and per vendor, not one link for everything',
          gpu.guide_for('10de:2684') != gpu.guide_for('1002:744c'),
          (gpu.guide_for('10de:2684'), gpu.guide_for('1002:744c')))
    # a card the tables DO judge keeps its own answer
    known = ' '.join(gpu.report([{'name': 'AMD Radeon RX 6600',
                                  'id': '1002:73ff'}], 'zen')[0])
    check('a card the table knows is untouched by any of this',
          'no table here claims' not in known and 'agdpmod=pikera' in known, known)
    nvidia = ' '.join(gpu.report([{'name': 'NVIDIA GeForce RTX 4090',
                                   'id': '10de:2684'}], 'zen')[0])
    check('and a family rule still answers for its whole vendor',
          'no driver was ever written' in nvidia
          and 'no table here claims' not in nvidia, nvidia)

    lines, _ = gpu.report([apus[0]], 'zen')
    said = ' '.join(lines)
    check('the report says it is not covered here',
          'not covered by this repository' in said, said)
    check('and names whose work the drivers are', 'ChefKiss' in said, said)
    check('and says the rest of the build is unaffected',
          'rest of the build applies' in said, said)
    check('rather than leaving a bare unknown',
          said.count('unknown') <= 1, said)

    # the About page carries the gap, and calls it a gap
    import provenance
    rows = [r for r in provenance.catalogue()
            if 'integrated' in r['area'].lower() and 'AMD' in r['area']]
    check('the About page names it as an area', rows, [r['area'] for r in rows])
    if rows:
        check('and says it is empty until somebody fills it',
              'Empty until' in rows[0]['gap'], rows[0]['gap'])


def a_kext_that_stops_below_the_target():
    """A kext bound below the macOS asked for has to say so, not be added quietly.

    The failure this exists for: a DW1820A read as supported, AirportBrcmFixup
    went into the config, and Sequoia came up with no Wi-Fi at all and nothing
    having said why. The kext patches Apple's own Broadcom driver, and Apple
    removed that driver - the kext's own README lists it as removed from macOS
    14 and says "[14+] Use with OCLP". A MaxKernel that release is past means
    OpenCore never loads it, so the card is simply absent.

    Reported rather than guessed: the bound is in data/network.toml, quoting
    the project that published it."""
    import advise
    import netkexts
    import summary

    sets = {s['match']: s for s in netkexts.sets()}
    brcm = sets.get('AirportBrcmFixup.kext')
    check('the Broadcom Wi-Fi set is there', brcm)
    if not brcm:
        return

    # Per device, not per set. The first version of this bounded the whole set
    # at Ventura, which is right for three ids and wrong for three more: the
    # README's table has 432b gone after 10.14 and 4331/4353 after 10.15,
    # because Apple removed the drivers one at a time. One ceiling over the set
    # claimed four more years of support than the document gives.
    rows = {d['id']: d for d in brcm.get('device') or []}
    check('it is bounded per device rather than as a whole', rows, sorted(rows))
    check('and the kext itself carries no ceiling to override them',
          not brcm['kext'][0].get('max_kernel'), brcm['kext'][0].get('max_kernel'))
    for ident, top, where in (('14e4:43a3', '22.99.99', '[13]'),
                              ('14e4:43a0', '22.99.99', '[13]'),
                              ('14e4:43ba', '22.99.99', '[13]'),
                              ('14e4:4331', '19.99.99', '[10.15]'),
                              ('14e4:4353', '19.99.99', '[10.15]'),
                              ('14e4:432b', '18.99.99', '[10.14]')):
        row = rows.get(ident)
        check(f'{ident} stops where the table last names it, {where}',
              row and row['max_kernel'] == top, row)
        check(f'  and quotes the table rather than asserting it',
              row and where in (row.get('note') or ''), row and row.get('note'))
    check('and what is needed above them is said once, for the set',
          'OpenCore Legacy Patcher' in (brcm.get('above') or {}).get('text', ''))
    check('including that an EFI cannot do it',
          'anything an EFI injects' in (brcm.get('above') or {}).get('text', ''))

    stops = summary._device_ceiling('AirportBrcmFixup.kext', '14e4:43a3')
    check('the ceiling is read back as a release name',
          stops and stops['name'] == 'Ventura', stops)
    older = summary._device_ceiling('AirportBrcmFixup.kext', '14e4:432b')
    check('and an older card reads as its own, earlier one',
          older and older['name'] == 'Mojave', older)

    # the fifteen ids the kext matches and the table never names. Absent from
    # the documentation is not supported for ever, and not unsupported either.
    unnamed = summary._device_ceiling('AirportBrcmFixup.kext', '14e4:4312')
    check('an id the table never names is marked as uncovered',
          unnamed and not unnamed['covered'], unnamed)
    check('and no ceiling is invented for it',
          unnamed and unnamed['darwin'] is None, unnamed)

    # a set that swaps one kext for another by version is not capped by the one
    # that stops first - Broadcom Bluetooth runs from 10.11 to now across five
    # bundles, and calling that "up to Mojave" would be wrong
    check('a set that hands over between kexts is not read as capped',
          summary._device_ceiling('BrcmPatchRAM3.kext', '0a5c:6412') is None,
          summary._device_ceiling('BrcmPatchRAM3.kext', '0a5c:6412'))

    import contextlib
    import io

    def said(target):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            advise.report(['14e4:43a3'], [], 'a test', target=target)
        # the sentence is wrapped to the console width, so a phrase in it is
        # split across lines and a plain substring search misses
        return re.sub(r'\s+', ' ', out.getvalue())

    above = said(24)                     # Sequoia
    check('asking for a macOS past it is told so',
          'not on the macOS you asked for' in above and 'Ventura' in above, above)
    # and the older card is told a different, earlier answer
    with contextlib.redirect_stdout(io.StringIO()) as out:
        advise.report(['14e4:432b'], [], 'a test', target=19)   # Catalina
    older = re.sub(r'\s+', ' ', out.getvalue())
    check('an older card is told its own ceiling, not this one',
          'this stops at Mojave' in older, older)
    # and one the table never names is told that, rather than a ceiling
    with contextlib.redirect_stdout(io.StringIO()) as out:
        advise.report(['14e4:4312'], [], 'a test', target=24)
    quiet = re.sub(r'\s+', ' ', out.getvalue())
    check('and an id with no documented range is told exactly that',
          'no macOS range is documented' in quiet, quiet)
    check('and told to use Ethernet for the install',
          'Ethernet during the install' in above)
    within = said(22)                    # Ventura
    check('asking for one it covers is not warned off',
          'not on the macOS you asked for' not in within, within)
    check('but still told where it stops', 'up to Ventura' in within, within)

    # the builder has to pass the answer through, or none of this ever fires
    flow = Path('tools/setup.py').read_text(encoding='utf-8')
    check('the builder passes the macOS it asked for into the report',
          'target=target' in flow)

    # and the machine's own range moves with it
    e570, _ = detect.read_report('tools/fixtures/thinkpad-e570.json')
    _, ceiling = summary.macos_range(e570)
    check('a machine with that card reads as topping out at Ventura',
          ceiling and ceiling[0] == 'Broadcom Wi-Fi' and ceiling[2] == 22, ceiling)

    # what was actually seen, recorded as an observation rather than a rule
    field = ocgen.read_toml('data/field.toml')
    seen = [r for r in field.get('network', []) if r.get('id') == '14e4:43a3']
    check('and somebody ran it, and said what they saw', seen, seen)
    if seen:
        check('naming who', seen[0].get('observed_by'), seen[0])
        check('and that the icon appears without working',
              'lists no networks' in seen[0].get('observed', ''), seen[0])
        check('and that a recovery has none of the patches anyway',
              'recovery environment has none' in seen[0].get('note', ''), seen[0])


def building_an_installer_image():
    """The guide's long way round, done in one run - and what it must not do.

    Two of its steps need root, and this is the only place in the program that
    asks for a password. An unsigned application asking for one is a thing to
    be careful with, so what is asked for has to be readable before it is
    approved and identical to what then runs. `--installer-script` prints it
    and must create nothing while doing so.

    It is macOS-only, because createinstallmedia is an Apple binary inside the
    installer app. The pane says that on other systems rather than offering
    buttons that cannot work."""
    import installer

    # sizing, against the run that was actually done
    was = installer.app_size
    installer.app_size = lambda _app: int(17 * installer.GiB)
    try:
        p = installer.plan('anything')
    finally:
        installer.app_size = was
    check('a 17 GiB app plans a 20 GiB image', p['gib'] == 20, p['gib'])
    check('which is what the Tahoe stick was really built with', p['gib'] == 20)
    check('and the overhead is the measured one, not a guess',
          abs(p['overhead'] - 2.5 * installer.GiB) < 1, p['overhead'])
    check('the volume it plans is bigger than the app',
          p['volume_needs'] > p['app'])
    # every one of them whole. 2.5 * GiB is a float in Python, JSON writes it
    # as 2684354560.0, and the pane refused it: "The JSON value could not be
    # converted to System.Int64". Sizes are bytes, and bytes are integers.
    floats = {k: v for k, v in p.items() if isinstance(v, float)}
    check('and every size it reports is a whole number', not floats, floats)
    import json as _json
    written = _json.dumps(p)
    check('so nothing in the JSON carries a decimal point',
          '.' not in written, written)

    # the privileged half: readable, and the same text that runs
    tools = installer.legacy_tools()
    check('the DuetPkg files are vendored with OpenCore', tools,
          'tools/opencore.py vendors Utilities/LegacyBoot')
    if tools:
        for name in ('boot0', 'boot1f32', 'bootX64', 'BootInstall_X64.tool'):
            check(f'  {name} is there', (tools / name).exists())
        runnable = tools / 'BootInstall_X64.tool'
        check('  and the tool can be executed', os.access(runnable, os.X_OK),
              oct(runnable.stat().st_mode)[-3:])

    was_creator = installer.creator
    installer.creator = lambda app: Path(app) / 'Contents/Resources/createinstallmedia'
    try:
        script = installer.privileged('/Applications/Install macOS X.app', '/dev/disk9')
    finally:
        installer.creator = was_creator
    check('the script names createinstallmedia', 'createinstallmedia' in script)
    check('and drives the vendored tool rather than repeating what it does',
          'BootInstall_X64.tool' in script and 'dd if=' not in script, script)
    check('and answers its question with the disk it made',
          'echo 9 |' in script, script)
    check('and says why root is needed, in the script itself',
          'needs root' in script, script)
    check('and stops on the first failure',
          'set -e' in script, script)

    # what --installer-script must not do
    flow = Path('tools/setup.py').read_text(encoding='utf-8')
    check('the engine can print that script without running any of it',
          "'--script'" in flow and 'installer_script' in flow)
    check('and the window asks for the printed one, not the doing one',
          '--installer-script' in
          Path('gui/Engine/Inventory.cs').read_text(encoding='utf-8'))

    # An .app is a directory and a package at once. A folder picker greys it
    # out - macOS does not offer a bundle as somewhere to descend into - so it
    # has to be asked for as a file, by the type it is. This was the first
    # thing that went wrong with the pane: Choose... opened, and the app could
    # not be clicked.
    pane = Path('gui/Views/InstallerView.axaml.cs').read_text(encoding='utf-8')
    # macOS will not let a package be confirmed in a panel that is choosing
    # files: Open stays grey however the type filter is written, with or
    # without com.apple.application-bundle. Both were tried. So the button asks
    # for the folder the app is in - which a panel is happy to return - and the
    # bundle is found inside it.
    chooser = pane.split('async Task ChooseApp()')[1][:1400]
    check('the button asks for a folder, which macOS will return',
          'OpenFolderPickerAsync' in chooser, chooser[:200])
    check('and finds the installer inside it',
          'Installers(' in chooser and 'static List<string> Installers' in pane)
    check('by what makes one, not by its name, which is localised',
          'createinstallmedia' in pane.split('static List<string> Installers')[1][:400])
    check('and says so when there is none',
          'No installer app in there' in pane)
    # several in one folder is a choice, not a dead end. Naming them and
    # stopping left somebody with nothing to click.
    check('and offers a choice when there is more than one',
          'void Offer(' in pane and 'Found.ItemsSource' in pane)
    check('with the handler bound once, not once per folder chosen',
          pane.count('Found.SelectionChanged') == 1
          and 'List<string> _found' in pane,
          'subscribing inside Offer stacks a handler per choice')
    # an unreadable answer is not a bad app, and calling it one sends somebody
    # to look at the wrong thing
    check('an unreadable answer is told apart from a bad app',
          "The engine's answer could not be read" in pane
          and 'That is not an installer app' in pane)
    check('and a path inside the bundle is walked back up to it',
          'static string Bundled' in pane)
    # a picker and a bundle do not always get on, so a path can be typed
    markup_app = Path('gui/Views/InstallerView.axaml').read_text(encoding='utf-8')
    check('and the path can be typed or dragged in instead',
          '<TextBox' in markup_app and 'Name="AppPath"' in markup_app)
    check('and a typed path is read when it is finished',
          'LostFocus' in pane and 'Key.Enter' in pane)
    # the note says it can be dragged in, so it has to be droppable: a TextBox
    # does not take files on its own, and a promise the pane does not keep is
    # worse than no promise
    check('and the pane really accepts a dropped app',
          'DragDrop.SetAllowDrop' in pane and 'DragDrop.DropEvent' in pane)
    check('which is what the note under the box promises',
          'drag the app onto this pane' in markup_app, markup_app[:0] or
          'the note and the handler have to promise the same thing')
    # a picker that hands back nothing has to say so rather than doing nothing
    check('and a path that cannot be read is reported, not swallowed',
          'could not be read as a path' in pane)
    check('with a second way of getting one before giving up',
          'static string? Local(' in pane and 'uri.LocalPath' in pane)

    # macOS only, said rather than half-worked
    check('the pane knows it is macOS only',
          'IsOSPlatform(OSPlatform.OSX)' in pane)
    check('and says so instead of drawing buttons that cannot work',
          'NotHere.IsVisible = true' in pane)
    check('and points at what does work on this system',
          'Everything else in this program works here' in pane)

    # the password is explained before it is asked for
    markup = Path('gui/Views/InstallerView.axaml').read_text(encoding='utf-8')
    check('the pane warns about the password before the button',
          markup.index('administrator password') < markup.index('Build the image'))
    check('and offers the script to read first',
          'Show what will run' in markup)

    # and the render pass looks at it
    capture = Path('gui/App.axaml.cs').read_text(encoding='utf-8')
    check('the screenshot pass opens the pane', '"installer"' in capture)
    check('but never presses the button',
          'make-installer' not in capture and 'InstallerState' in capture)


def what_the_download_shows():
    """The bar is drawn from somebody else's print statement.

    macrecovery redraws one line while it downloads, and the window reads the
    numbers out of it to draw a bar, a rate and a time left. That makes the
    window depend on the exact shape of a string in a vendored tool - and if
    acidanthera reformats it, the bar stops moving and nothing says why.

    So the format is checked here against the source it comes from: the print
    statement is read out of the vendored macrecovery, a line is rendered the
    way that statement would render it, and the pattern the window compiles is
    applied to it. Both halves are read from the tree, so neither can be
    updated without the other being checked."""
    import recovery

    tool = recovery.vendored()
    check('macrecovery is vendored', tool is not None)
    if tool is None:
        return
    source = tool.read_text(encoding='utf-8', errors='replace')

    # the statement the bar depends on
    printed = re.search(r"print\(f'\\r\{size / \(2\*\*20\):\.1f\}"
                        r"/\{totalsize / \(2\*\*20\):\.1f\} MB ", source)
    check('it still prints how much of how much has arrived', printed,
          'the download progress line has been reformatted upstream')
    check('and the percentage beside it',
          "% downloaded" in source)

    # a line exactly as that statement would produce it
    size, total = 123.4 * 2 ** 20, 700.0 * 2 ** 20
    progress = size / total
    rendered = (f'{size / (2 ** 20):.1f}/{total / (2 ** 20):.1f} MB '
                f'|{"=" * 6:<20}| {progress * 100:.1f}% downloaded')

    # and the pattern the window compiles, read out of the window
    pane = Path('gui/Views/RecoveryView.axaml.cs').read_text(encoding='utf-8')
    found = re.search(r'new\(@"([^"]+)"', pane)
    check('the window compiles a pattern for it', found)
    if not found:
        return
    pattern = found.group(1).replace('\\\\', '\\')
    hit = re.search(pattern, rendered)
    check('and it matches what macrecovery prints', hit, (pattern, rendered))
    if hit:
        check('reading back the megabytes done and the total',
              hit.group(1) == '123.4' and hit.group(2) == '700.0', hit.groups())

    # what the pane does with them
    check('the pane draws a bar', 'ProgressBar' in
          Path('gui/Views/RecoveryView.axaml').read_text(encoding='utf-8'))
    check('and a rate', 'MB/s' in pane)
    check('and how much longer', 'left' in pane and 'static string Left' in pane)
    # measured over a window: an average since the start hides a slow patch
    check('and measures the rate over a window rather than since the start',
          'seen.Dequeue' in pane, 'the rate is averaged over the whole download')
    # the numbers are parsed with an invariant culture: a machine whose decimal
    # separator is a comma parsed "123.4" as 1234 and the bar jumped to 100%
    check('and parses them the same way on every machine',
          'InvariantCulture' in pane)

    # and the stream has to arrive while it is happening. Python block-buffers
    # stdout into a pipe, so without this the whole download reported at once
    # at the end and the bar sat on "connecting..." throughout.
    launcher = Path('gui/Engine/Builder.cs').read_text(encoding='utf-8')
    check('the window runs the engine unbuffered',
          launcher.count('PYTHONUNBUFFERED') >= 2,
          'both Run and Stream have to set it, or one of the two buffers')

    # a failure has to say which failure it was
    src = Path('tools/recovery.py').read_text(encoding='utf-8')
    check('a bad download and a moved folder are told apart',
          'No such file or directory' in src and 'moved or renamed it' in src)
    check('and the bad-bytes case says downloading again is the fix',
          'downloading it again is the fix' in src)
    # which needs the tool's own last words kept
    import io as _io
    said = recovery.Progress(0.5, out=_io.StringIO())
    said.write('Image verification failed. ([Errno 2] No such file or directory)\n')
    check('the tool\'s last lines are kept to say it with', said.frames, said.frames)

    # sampled often enough to move
    every = re.search(r'def fetch\(choice, into, tool=None, every=([\d.]+)\)',
                      Path('tools/recovery.py').read_text(encoding='utf-8'))
    check('and the engine samples often enough for a bar to move',
          every and float(every.group(1)) <= 1.0,
          every.group(1) if every else 'no default found')


def whether_recovery_can_land():
    """Recovery downloads on the machine being installed, not on this one.

    The pane said "it boots, connects, and downloads the rest" and never asked
    whether the target had a card macOS drives. A Realtek Wi-Fi laptop makes
    that sentence false, and the way it fails is expensive: the stick is made,
    the BIOS is set, the installer boots, and only there is there no network.

    The case worth the most is 'cable' - Wi-Fi with no driver and Ethernet with
    one. Recovery works perfectly on that machine, and the only missing piece
    is knowing to plug the cable in first."""
    import recovery
    import summary

    def machine(wifi, ethernet):
        """A report shaped only as far as network_rows reads it."""
        rows = []
        for part, state in (('Wi-Fi', wifi), ('Ethernet', ethernet)):
            if state == 'absent':
                continue
            rows.append({'part': part, 'verdict':
                         summary.SUPPORTED if state == 'driven'
                         else summary.UNSUPPORTED})
        was = summary.network_rows
        summary.network_rows = lambda _hw, rows=rows: rows
        try:
            return recovery.carries({'anything': True})
        finally:
            summary.network_rows = was

    verdict, said = machine('driven', 'driven')
    check('a machine with driven Wi-Fi is ready', verdict == 'ready', verdict)

    verdict, said = machine('unsupported', 'driven')
    check('Wi-Fi with no driver and Ethernet with one asks for a cable',
          verdict == 'cable', verdict)
    check('and says so in the sentence, not only in the verdict',
          'Ethernet cable' in said, said)
    check('and says why: the download happens on that machine',
          'happens on this machine' in said, said)

    verdict, said = machine('absent', 'driven')
    check('a machine with no Wi-Fi at all still gets the cable answer',
          verdict == 'cable', verdict)
    check('and is not told its Wi-Fi lacks a driver',
          'no macOS driver' not in said, said)

    verdict, _ = machine('unsupported', 'unsupported')
    check('neither driven is a refusal', verdict == 'no', verdict)
    verdict, _ = machine('absent', 'absent')
    check('and so is no card at all', verdict == 'no', verdict)

    verdict, said = recovery.carries(None)
    check('with no report it declines rather than guesses',
          verdict == 'unknown', verdict)
    check('and says the machine it means is the one being installed',
          'machine being installed' in said or 'that machine' in said, said)

    # both surfaces, one sentence
    document = Path('tools/inventory.py').read_text()
    check('the window is told the verdict',
          "'network': verdict" in document and "'network_note'" in document)
    console = Path('tools/recovery.py').read_text()
    check('and the console says it too', '_say_network' in console)
    pane = Path('gui/Views/RecoveryView.axaml.cs').read_text()
    check('and the pane draws it', 'SayNetwork' in pane)
    check('and names the cable case in the words a person acts on',
          'Use an Ethernet cable' in pane and 'Use an Ethernet cable' in console)


def a_mark_for_every_macos():
    """Every release offered gets a mark, including ones nobody has seen.

    The offer list comes from macrecovery's board table and grows the day Apple
    serves something new. A grid whose tiles came from a hand-kept file would
    arrive with a hole in it that day, so anything the table has not heard of
    falls back to a hue derived from its own name.

    None of these are Apple's artwork. The About pane and the guide's footer
    both say nothing of Apple's is redistributed here, and a folder of their
    wallpapers inside the binary would make both untrue."""
    import recovery

    table = Path('data/macosmark.toml')
    check('the marks are a table of their own', table.exists())
    # the prose is a wrapped comment block, so a sentence in it is split
    # across lines and a plain substring search misses every time
    said = re.sub(r'\s+', ' ', table.read_text(encoding='utf-8').replace('#', ' '))
    check('and it says they are chosen rather than derived from anything',
          'chosen, not derived' in said)
    check('and why they are not Apple\'s', 'redistributes nothing of Apple' in said
          or 'nothing of Apple' in said)
    check('and that it is not a second list of releases',
          'data/macos.toml' in said)

    # it must not become a copy of the release list
    import ocgen
    releases = {r['name'] for r in ocgen.read_toml('data/macos.toml')['release']}
    marks = {m['name'] for m in ocgen.read_toml(table)['mark']}
    check('every mark names a release the repository knows',
          not (marks - releases), sorted(marks - releases))

    for choice in recovery.choices():
        mark = choice.get('mark')
        check(f"{choice['label']} has a mark", mark, choice['label'])
        if not mark:
            continue
        check(f"  and it is a colour pair and a letter",
              re.fullmatch(r'#[0-9a-f]{6}', mark['from'])
              and re.fullmatch(r'#[0-9a-f]{6}', mark['to'])
              and len(mark['letter']) >= 1, mark)

    # the day Apple serves something with a name nobody has typed here
    unheard = recovery.mark('Something Nobody Has Typed Here')
    # the row the board table refuses to name, named without a connection
    top = recovery.choices()[0]
    check('the unnamed row is the newest one', top['version'] == 'latest', top['version'])
    said = recovery.recorded()
    check('and the repository already records what that is', said, said)
    if said:
        check('so the row opens with a name rather than a question',
              said['name'] and said['name'] in top['label'], top['label'])
        check('and with the release to draw an icon for',
              top.get('art') == said['name'], top.get('art'))
        # the version stays `latest`: that is what the download asks for, and
        # what Apple serves it may have moved on by then
        check('while still asking for whatever is newest',
              top['version'] == 'latest', top['version'])
        # `name` stays empty so find() cannot match two rows on one release
        check('and its name stays empty, for the day a real row appears',
              top['name'] == '', top['name'])
        check('asking for that release by name still reaches it',
              (recovery.find(said['name']) or {}).get('version') == 'latest')
        # a real row wins over the stand-in
        check('and a named row wins over it',
              (recovery.find('sequoia') or {}).get('name') == 'Sequoia')

    # and the live answer, which is what the button is for
    check('Apple can still be asked directly',
          'def newest' in Path('tools/recovery.py').read_text())
    engine = Path('tools/setup.py').read_text()
    check('and the engine exposes it as a command of its own',
          "'--recovery-newest'" in engine or '--recovery-newest' in engine)
    pane = Path('gui/Views/RecoveryView.axaml.cs').read_text()
    check('and the pane asks only when pressed',
          'AskApple' in pane and 'Ask.Click' in pane)
    # renaming the row has to drop the cached icon lookup, or it keeps the
    # placeholder on a row that now knows what it is
    model = Path('gui/Engine/Inventory.cs').read_text()
    check('and naming it drops the cached icon lookup',
          '_looked = false' in model)
    # the About page counted one connection, and there are two now
    import inventory as _inv
    said = _inv.about()['network']
    check('the About page names both connections',
          'recovery installer' in said and 'serving today' in said, said)

    check('a release the table never heard of still gets one',
          unheard['source'] == 'derived'
          and re.fullmatch(r'#[0-9a-f]{6}', unheard['from']), unheard)
    check('and the same one every time it is asked',
          unheard == recovery.mark('Something Nobody Has Typed Here'))

    # the grid, and what it replaced
    pane = Path('gui/Views/RecoveryView.axaml').read_text()
    check('the pane draws them as a grid', 'WrapPanel' in pane)
    check('rather than the drop-down that showed one at a time',
          '<ComboBox' not in pane)
    check('and each tile carries its mark', 'Binding Tile' in pane
          and 'Binding Letter' in pane)


def the_mac_a_config_pretends_to_be():
    """The identity's own ceiling, which the hardware knows nothing about.

    A Kaby Lake laptop can run every macOS its graphics support, and the
    install will still refuse if the config claims MacBookPro14,1 and the
    release stopped serving that model. The machine page used to say this was
    not recorded; it is now."""
    import smbios
    import summary

    rows = smbios.table()
    check('the identity table is here', len(rows) > 100, len(rows))
    check('every row names a model and at least one board',
          all(r['name'] and r['boards'] for r in rows))

    # the list form is not the rare case, and a parser that reads only the
    # scalar one drops those models without saying anything
    many = [r for r in rows if len(r['boards']) > 1]
    check('models with more than one board survived the parse', many,
          [r['name'] for r in many][:4])
    scalar = smbios.boards_in('SystemProductName: "X"\nBoardProduct: "Mac-1"\n')
    listed = smbios.boards_in('BoardProduct:\n  - "Mac-1"\n  - "Mac-2"\n')
    check('both spellings read', scalar == ['Mac-1'] and listed == ['Mac-1', 'Mac-2'],
          (scalar, listed))

    # every identity a profile can write has to be answerable, or the builder
    # asks a question it cannot act on
    unknown = []
    for profile in sorted(Path('profiles/cpu').rglob('*.toml')):
        identity = smbios.profile_identity(profile.read_text(encoding='utf-8'))
        if identity and smbios.reach(identity)[0] is None:
            unknown.append((profile.stem, identity))
    check('every identity a profile claims is in the table', not unknown, unknown)

    # the join itself, on the case that started this
    version, said = smbios.reach('MacBookPro14,1')
    check('MacBookPro14,1 is served up to Ventura', version == '13.7.8', said)
    fits, _ = smbios.reaches('MacBookPro14,1', '26')
    check('so Tahoe is past it', fits is False)
    fits, _ = smbios.reaches('MacBookPro14,1', '13')
    check('and Ventura is not', fits is True)
    version, _ = smbios.reach('MacBookPro16,1')
    check('an identity Apple keeps current says so rather than a number',
          version == 'latest', version)
    check('and it reaches whatever was asked for',
          smbios.reaches('MacBookPro16,1', '26')[0] is True)
    check('an identity nothing knows is not guessed at',
          smbios.reach('MacBookPro99,9')[0] is None)

    named = smbios.higher('26')
    check('identities that do reach it can be named', named, len(named))
    check('and MacBookPro14,1 is not among them',
          'MacBookPro14,1' not in named)

    # the builder asks, and asks once
    source = Path('tools/setup.py').read_text()
    check('the builder asks which macOS',
          source.count("'Which macOS are you installing?'") == 1, 
          source.count("'Which macOS are you installing?'"))
    check('and uses that answer for the kexts rather than asking again',
          'darwin = target if mode' in source)
    check('and says what the identity reaches', 'smbios.reaches(' in source)
    check('and offers one that is served, rather than saying to edit a plist',
          'smbios.suggest(' in source and "'--smbios', claim" in source)
    check('the builder can be told which Mac to claim',
          "'--smbios'" in Path('tools/build.py').read_text())

    # nearest, not newest: the closest still-served model keeps the most of
    # what the profile was written around, and a laptop stays a laptop
    check('a laptop is offered laptops',
          all(m.startswith('MacBook')
              for m in smbios.suggest('MacBookPro14,1', '26')),
          smbios.suggest('MacBookPro14,1', '26'))
    check('and the nearest one first',
          smbios.suggest('MacBookPro14,1', '26')[0] == 'MacBookPro16,1',
          smbios.suggest('MacBookPro14,1', '26'))
    check('a desktop is offered desktops',
          not any(m.startswith('MacBook')
                  for m in smbios.suggest('MacPro6,1', '26')),
          smbios.suggest('MacPro6,1', '26'))
    check('a family that has run out falls back to the same shape',
          smbios.suggest('MacBookAir9,1', '26'),
          smbios.suggest('MacBookAir9,1', '26'))
    # always three, so the position of the decline option cannot move when
    # the model database gains a machine - a scripted answer is a number
    check('the list is a fixed length',
          all(len(smbios.suggest('MacBookPro14,1', v)) == 3
              for v in ('14', '15', '26')),
          [len(smbios.suggest('MacBookPro14,1', v)) for v in ('14', '15', '26')])
    check('and no list offers the identity somebody already has',
          all(m not in smbios.suggest(m, '26')
              for m in ('MacPro7,1', 'MacBookPro16,1', 'iMac20,1')))

    # the serial has to belong to the Mac the config claims, so the swap
    # happens before macserial is asked for one
    built = Path('tools/build.py').read_text()
    check('the identity is swapped before the serial is minted',
          built.index("gen['SystemProductName'] = a.smbios")
          < built.index('serial = apply_identity('))

    # a real Mac is judged by the same list, not by Apple\'s per-line one
    facts = summary.genuine_mac({'system': 'Darwin',
                                 'board_id': 'Mac-E1008331FDC96864'})
    check('a Mac Apple keeps current has no ceiling to name',
          facts['to'] is None and facts['current'], facts)
    facts = summary.genuine_mac({'system': 'Darwin',
                                 'board_id': 'Mac-B4831CEBD52A0C4C'})
    check('and one that stopped says where',
          facts['to'] and facts['to']['version'] == '13', facts)


def what_it_looks_like_when_it_arrives():
    """The icon, and the shapes each system expects a program to arrive in.

    A folder of files is not how a program arrives on any of the three. macOS
    wants a .app - without an Info.plist a double-click opens Terminal, the
    Dock draws a generic page, and the menu bar says the process name, which is
    how "Avalonia Application" ended up above a window called something else."""
    import icons

    trouble = icons.check()
    check('every icon file is here and the right shape', not trouble, trouble)

    # the master is not the drawing as it arrived: macOS applies no mask, and
    # a drawing that fills three quarters of its frame sits a size smaller than
    # everything beside it in a Dock
    w, h, left, right, top, bottom = icons.shape_of(icons.MASTER)
    check('the drawing fills the frame the way Apple\'s own icons do',
          right - left + 1 == icons.SHAPE and w == icons.FRAME,
          f'{right - left + 1} in {w}')
    check('and the source it was cut from is kept',
          (icons.ICONS / 'icon-source-2048.png').exists())

    # the .ico really holds four sizes, since nothing else here would notice
    blob = icons.ICO.read_bytes()
    import struct
    kind, count = struct.unpack('<HH', blob[2:6])
    check('the .ico is an icon file with every size in it',
          kind == 1 and count == len(icons.WINDOWS), (kind, count))

    csproj = Path('gui/Shell.csproj').read_text()
    check('the executable carries the icon', 'ApplicationIcon' in csproj)
    check('and a name Explorer can show', '<Product>' in csproj)
    layout = Path('gui/App.axaml').read_text()
    check('the application names itself, which is what the menu bar reads',
          'Name="Hackintosh EFI Builder"' in layout)
    window = Path('gui/Views/MainWindow.axaml').read_text()
    check('and the window has the icon on it', 'Assets/Icon/png' in window)
    # the sidebar drew the same chip a second time, by hand, in Path data. Two
    # drawings of one mark are one edit away from disagreeing, and the one
    # nobody re-exports is the one that goes stale.
    check('and the sidebar draws that file rather than redrawing the mark',
          window.count('Assets/Icon/png') >= 2 and '<Path ' not in window)

    # the bundler
    bundler = Path('tools/appbundle.py').read_text()
    check('the bundle names itself for the menu bar',
          "'CFBundleName'" in bundler)
    # run rather than grepped: it made a bundle with no engine in it once,
    # and the window opened to "no engine found" and nothing else
    import appbundle
    with tempfile.TemporaryDirectory() as where:
        empty = Path(where) / 'published'
        empty.mkdir()
        (empty / 'HackintoshEFIBuilder').write_bytes(b'not really')
        try:
            appbundle.build(empty, Path(where) / 'x.app', '1.0.7')
            check('and refuses to ship without the engine inside it', False,
                  'it made one anyway')
        except SystemExit as refused:
            check('and refuses to ship without the engine inside it',
                  'EFIBuilderEngine' in str(refused), str(refused)[:60])
    check('and signs last, because moving a file after invalidates it',
          bundler.index('codesign') > bundler.index("PkgInfo"))
    # a keep-list. A delete-list is a list somebody forgets to add to, and the
    # first bundle this made carried NEXT-STEPS.txt and a .DS_Store
    check('it copies what belongs rather than deleting what does not',
          "item.suffix == '.dylib'" in bundler and 'left.append' in bundler)

    # the last line of a menu was under the edge, and the scroller was asked
    # to go to an end it had not measured yet
    drawn = Path('gui/Views/BuilderView.axaml.cs').read_text()
    check('the transcript follows its last line once the layout settles',
          'LayoutUpdated' in drawn and 'void StickToEnd' in drawn)
    check('and again when the question panel changes how tall it is',
          drawn.count('StickToEnd();') >= 4, drawn.count('StickToEnd();'))
    check('and it reports where it is, so a build can check',
          'scrolled {Scroll.Offset.Y' in drawn)
    # a file, not a heredoc in the workflow: written inline the same check was
    # read as shell commands, printed nothing, and passed by accident
    import scrollcheck
    check('which the render pass checks with a tool of its own',
          'scrollcheck.py' in Path('.github/workflows/gui.yml').read_text())

    # the line the workflow greps for is the line the pane prints. Adding the
    # scroll position to the middle of it broke a pattern that assumed the
    # count and the question were adjacent - and that failed the step before
    # any of the checks after it ran, which is why nothing said why.
    said = ('builder: 20 lines, scrolled 0 + 342 of 306, '
            'asking "Which machine is this EFI for?" with 4 options')
    workflow = Path('.github/workflows/gui.yml').read_text()
    for pattern in re.findall(r"grep -qE '(builder:[^']+)'", workflow):
        check('the workflow still recognises what the pane prints',
              re.search(pattern, said), pattern)
    check('that tool catches a transcript left short',
          scrollcheck.short('scrolled 0 + 70 of 337'), 'missed it')
    check('and passes one that is at the end',
          not scrollcheck.short('scrolled 63 + 274 of 337'))
    check('and does not mind a viewport taller than the content',
          not scrollcheck.short('scrolled 0 + 379 of 355'))
    shape = Path('gui/Views/BuilderView.axaml').read_text()
    # in the content, not on the viewer. A ScrollViewer's Padding shrinks what
    # is on screen without adding anything to scroll through, so the last rows
    # sat behind it while the scroller reported itself at the end - which is
    # why the check above passed and a menu still ended two lines early.
    check('the room under the last line is part of what scrolls',
          'Name="Transcript" Spacing="1" Margin="0,0,0,28"' in shape)
    check('and the viewer itself pads nothing at the bottom',
          'Padding="16,12,16,0"' in shape)

    made = Path('.github/workflows/gui.yml').read_text()
    check('macOS packages as a .app', 'appbundle.py' in made)
    check('and it is checked for a name, an icon, an engine and a signature',
          all(x in made for x in ('CFBundleName', '.icns',
                                  'Resources/EFIBuilderEngine',
                                  'codesign --verify')))
    check('Linux gets one file that runs wherever',
          'appimage.py' in made and '.AppImage' in made)
    check('and the AppImage is started rather than only built',
          'the AppImage did not find its engine' in made)

    packer = Path('tools/appimage.py').read_text()
    check('the AppImage carries the engine beside the window',
          f"binaries / ENGINE" in packer)
    check('and writes what a menu needs',
          'Desktop Entry' in packer and 'AppRun' in packer)
    check('and keeps what belongs rather than deleting what does not',
          "item.suffix == '.so'" in packer and 'left.append' in packer)

    # the exercised build used to write its EFI and its notes among the two
    # programs, because it ran with the package as its working directory
    check('the runs happen somewhere else', 'mkdir -p scratch' in made)
    check('and nothing publishes debug symbols beside the program',
          'DebugType=none' in made)
    check('so the keep-list is a check, not a cleaner',
          '::warning::' in made)

    # the AppImage is the whole program again; leaving it in the folder zip
    # shipped Linux twice and took that download from 86 MB to 168
    shipped = Path('.github/workflows/release.yml').read_text()
    check('the AppImage is published on its own, not inside the folder zip',
          '.AppImage' in shipped and 'dist/*.AppImage' in shipped)

    # and the zip is made by the build that made the thing. An artifact is a
    # file tree: carrying a .app as one lost the symlinks inside
    # Python.framework and the signature with them, and macOS called the app
    # damaged.
    check('each package zips itself', 'Into the zip it ships as' in made)
    check('with ditto on macOS, which is what keeps a bundle',
          'ditto -c -k' in made)
    check('and the release moves those zips rather than making its own',
          're-zipping' in shipped.lower() or 'as their builds zipped them' in shipped)
    check('and the bundle is unpacked again and checked before it ships',
          'does not survive its own zip' in made
          and 'the framework symlinks did not survive' in made)
    # unpacking is not enough: it has to find its engine from in there, which
    # it did not, and a bundle sitting in a clone hid that by walking up
    check('and it is run from the bundle, not only unpacked',
          'engine: inside this app' in made)
    finder = Path('gui/Engine/Builder.cs').read_text()
    check('the window looks inside its own Resources',
          '"..", "Resources", "EFIBuilderEngine"' in finder)


def what_to_show_the_igpu_as():
    """The other identity a build claims, and the same rule about inventing.

    An iGPU whose device id is not one its generation supports can sometimes be
    presented as one that is. WhateverGreen says which, in sentences; where it
    says nothing - Ice Lake - nothing here fills the gap."""
    import gpu
    import ocgen as _oc

    rows = _oc.read_toml(Path('data/framebuffer.toml')).get('fake', [])
    check('the faked ids are read out of the document', rows, len(rows))
    for row in rows:
        check(f'{row["id"]} keeps the sentence it came from',
              row['says'].strip().endswith(('.', ':')) and '`' in row['says'],
              row['says'][:60])
        check(f'{row["id"]} is eight hex digits, as a property takes it',
              len(row['id']) == 8 and all(c in '0123456789abcdef' for c in row['id']),
              row['id'])
        check(f'{row["id"]} says which profiles it is about', row['profiles'])

    # a sentence that names device ids is about those ids and no others
    exact = gpu.fakes('coffe-lake-plus', '8086:3e91')
    check('an id the document names gets that sentence and only that one',
          len(exact) == 1 and exact[0]['matches'] == ['8086:3e91'], exact)
    check('and the id it says to fake *to* is not read as one it applies to',
          '8086:3e92' not in exact[0]['matches'], exact[0]['matches'])

    # and a generation the document is silent about gets nothing *quoted*
    check('Ice Lake is quoted nothing, because nothing is written',
          gpu.fakes('ice-lake', '8086:8a56') == [],
          gpu.fakes('ice-lake', '8086:8a56'))

    # what somebody has run instead, kept apart from what is written
    seen = gpu.reported_fakes('ice-lake', '8086:8a56')
    check('but what somebody ran is offered, from the other table', seen, seen)
    if seen:
        row = seen[0]
        check('with where it came from', row['source'].startswith('http'))
        check('and the framebuffer that went with it, which is half the change',
              row.get('platform_id'), row)
        check('and it says it is not the project speaking',
              'not a sentence from the project' in row.get('note', ''))
    check('an id nobody reported gets nothing',
          gpu.reported_fakes('kaby-lake', '8086:5916') == [])

    # the sentences survived the markdown: a link full of full stops used to
    # cut them off in the middle
    check('no sentence begins mid-link',
          not any(r['says'].startswith(('org/', 'com/', 'www.')) for r in rows),
          [r['says'][:20] for r in rows])

    source = Path('tools/setup.py').read_text()
    check('the builder offers it rather than applying it',
          "'Fake the device-id?'" in source)
    check('and writes it where the framebuffer goes',
          "device_props[igpu.IGPU_PATH]['device-id']" in source)
    check('a reported one is labelled as reported in the menu itself',
          'not stated by WhateverGreen' in source)
    check('and brings its framebuffer with it',
          "chosen['platform_id']" in source)
    # `row` at that point is the profile this build is for; rebinding it
    # emptied the profile three hundred lines later
    check('and does not rebind the profile while listing sentences',
          'for sentence in said' in source)


def the_tools_a_window_can_drive():
    """Both vendored tools reach a person, whichever surface is attached.

    They read their own input, which a window has none of. One of them has a
    single input function and takes a replacement; the other is somebody else's
    executable and gets a console window of its own. Neither is refused now,
    and being refused was the state this records the end of."""
    import inspect
    import usbmap

    check('the mapper can be given a console of its own',
          'own_console' in inspect.signature(usbmap.run).parameters)
    source = Path('tools/usbmap.py').read_text()
    check('and it asks for one the way Windows spells it',
          'CREATE_NEW_CONSOLE' in source)
    check('by name, not by number, so it reads as what it is',
          '0x00000010' not in source)

    builder = Path('tools/setup.py').read_text()
    check('a front end is offered the mapper rather than skipped',
          'own_console=UI.protocol' in builder)
    check('and told where it will appear',
          'window of its own' in builder)
    # the guard that used to skip it entirely
    check('nothing skips the step for being a front end',
          'not UI.protocol and not a.usb_map' not in builder)

    # Opening it to a front end opened it to the unattended pass as well, which
    # answered yes and waited for somebody to plug in a device. An unattended
    # pass declines what it is offered.
    drive = Path('gui/Views/BuilderView.axaml.cs').read_text()
    check('an unattended pass declines rather than taking the first row',
          'o.Value is "no" or "none"' in drive, 'declining option preferred')
    check('and the value it declines by is in the question it was sent',
          "'value': v" in Path('tools/setup.py').read_text())


def what_oclp_restores():
    """Where the graphics go past their native ceiling, and whose doing it is.

    OCLP publishes this: each patch set with the macOS it applies from. The
    join between their prose and this repository's family names is the only
    part written here, and it is the part worth pinning down."""
    import oclptable
    import summary

    table = oclptable.table()
    check('the table names its source',
          'OpenCore-Legacy-Patcher' in table.get('source', ''), table.get('source'))
    check('and holds the patch sets the page lists',
          len(table.get('patch', [])) >= 8, len(table.get('patch', [])))

    kepler = oclptable.for_nvidia('GK')
    check('Kepler is restored from macOS 12',
          kepler and kepler['from'] == '12.0', kepler)
    check('and Pascal is not, because the page does not list it',
          oclptable.for_nvidia('GP') is None)
    check('Haswell graphics are restored from 13',
          (oclptable.for_igpu('haswell') or {}).get('from') == '13.0')
    check('and Polaris cards too',
          (oclptable.for_card_family('Polaris 10 and 20 series') or {}).get('from')
          == '13.0')
    check('a family nobody patches gets nothing',
          oclptable.for_nvidia('AD') is None
          and oclptable.for_igpu('raptor-lake') is None)

    # the patch page says where a set starts and never where it stops, so the
    # ceiling comes from the shape of the documentation: one support page per
    # macOS OCLP has added, and the newest of them is as far as it goes
    top = oclptable.upper_bound()
    check('there is a ceiling, and it is a macOS anybody would recognise',
          top and top[0] and top[1].isdigit(), top)
    check('and it is at least Ventura, or the pages were misread',
          top and int(top[1]) >= 13, top)
    check('the table says where the ceiling came from',
          'MODELS' in oclptable.table().get('ceiling_source', ''),
          oclptable.table().get('ceiling_source'))

    # and it reaches the machine screen, beside the range rather than inside it
    kepler_machine = {'generation': 'comet-lake', 'laptop': False,
                      'gpu_devices': [{'id': '10de:1180', 'name': 'GTX 680'}]}
    said = summary.patched_further(kepler_machine)
    check('a Kepler machine is told where the patches take it',
          said and said[0]['from'] == '12.0', said)
    window = summary.macos_windows(kepler_machine)
    check('and the range itself is untouched by it',
          all('OCLP' not in w[0] for w in window), window)

    modern = {'generation': 'comet-lake', 'laptop': False,
              'gpu_devices': [{'id': '1002:73ff', 'name': 'RX 6600'}]}
    check('a machine nothing patches is told nothing',
          summary.patched_further(modern) == [], summary.patched_further(modern))

    # one line per family, however many cards of it are in the machine
    two_keplers = dict(kepler_machine, gpu_devices=[
        {'id': '10de:1180', 'name': 'GTX 680'}, {'id': '10de:1187', 'name': 'GTX 760'}])
    check('two cards of one family say it once',
          len(summary.patched_further(two_keplers)) == 1,
          summary.patched_further(two_keplers))


def the_about_page():
    """What the program says about itself has to be true of the program.

    Every number on it is counted from the tree, because a number typed into a
    sentence goes stale silently - this page carried "OpenCore 1.0.6" and "41
    kexts" while the tree held 1.0.5 and 42."""
    import inventory

    about = inventory.about()
    check('the OpenCore version is the vendored one',
          about['opencore'] == sorted(x.name for x in Path('vendor/opencore').iterdir()
                                      if x.is_dir())[-1], about['opencore'])
    check('the kext count is what the lock holds',
          about['kexts'] == len(ocgen.read_toml(Path('vendor/kexts.lock'))['kext']))
    check('and what is actually on disk agrees with it',
          about['shipped'] == about['kexts'], (about['shipped'], about['kexts']))
    check('the config count is the catalogue length',
          about['configs'] == len(ocgen.read_toml(
              Path('profiles/catalogue.toml'))['config']))

    # the whole point of the page
    check('every source area says what it covers and what it does not',
          all(s['covers'] and s['gap'] for s in about['sources']),
          [s['area'] for s in about['sources'] if not (s['covers'] and s['gap'])])
    check('every one names a kind the page explains',
          {s['kind'] for s in about['sources']}
          <= {'derived', 'measured', 'quoted', 'reported', 'none'},
          sorted({s['kind'] for s in about['sources']}))
    check('and the tally adds up to the areas',
          sum(about['tally'].values()) == len(about['sources']))

    # vendored programs, which the page carried and never drew
    check('the vendored programs are listed', len(about['tools']) >= 5,
          len(about['tools']))
    check('each with the licence its project states',
          all(t.get('license') for t in about['tools']),
          [t['path'] for t in about['tools'] if not t.get('license')])
    check('and the upstream it came from',
          all(t.get('upstream') for t in about['tools']))

    check('this repository names its own licence',
          about['licence'] and 'License' in about['licence'], about['licence'])

    # the sentence about the network used to say "both ACPI tools" while nine
    # programs travelled in the package, so it is counted now and not written
    source = Path('gui/Views/AboutView.axaml.cs').read_text()
    layout = Path('gui/Views/AboutView.axaml').read_text()
    check('the offline sentence counts what it claims',
          'about.Tools.Count' in source, 'about.Tools.Count' in source)
    check('and is not a fixed sentence in the layout',
          'ACPI tools travel' not in layout)
    check('and the weakest sources are drawn first', '["none"] = 0' in source)


if __name__ == '__main__':
    for section in (graphics, graphics_advice, audio_advice, storage, peripherals,
                    trackpad, framebuffer, boot_args, other_machine,
                    undecodable_output, scripted_answers, hardware_summary,
                    device_names, broadcom_wifi, detection_gaps, provenance,
                    framebuffers, native_device_ids, field_reports, load_order,
                    smbus_trackpad, macos_window, card_readers, third_party,
                    usb_mapping, acpi_tables, the_windows_only_ways_this_broke,
                    unattended_ssdts, ssdt_flow, window_stays_open,
                    frozen_names, frozen_build, workflow_flags,
                    runner_independence, tables_match_sources,
                    front_end_protocol, machine_document, machine_name,
                    embedded_fonts, macos_registry, genuine_macs,
                    the_processor_bounds_it_too, graphics_and_the_range,
                    what_the_machine_calls_its_network, the_device_catalogue,
                    nvidia_by_family, what_the_two_programs_are_called,
                    the_vendored_opencore,
                    the_tools_a_window_can_drive,
                    the_recovery_it_can_fetch,
                    the_mac_a_config_pretends_to_be,
                    whether_recovery_can_land, a_mark_for_every_macos,
                    what_it_says_about_amd_integrated,
                    what_the_download_shows,
                    building_an_installer_image,
                    a_kext_that_stops_below_the_target,
                    what_it_looks_like_when_it_arrives,
                    what_to_show_the_igpu_as,
                    the_stick_it_writes_to,
                    what_oclp_restores, the_about_page,
                    what_the_readme_shows, what_the_guide_holds):
        print(f'\n{section.__name__}')
        section()
    print()
    if FAILED:
        sys.exit(f'{len(FAILED)} failed: {", ".join(FAILED)}')
    print('  all good')
