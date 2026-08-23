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
                 '--answers', '2,10,3', '--out', str(out)])
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
        r = run([sys.executable, 'tools/setup.py', '--answers', '3,2,10,3,1,3,1,1',
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
                 '--answers', '2,10,3,3', '--out', str(with_drive)])
        b = run([sys.executable, 'tools/setup.py', '--machine', fixture,
                 '--answers', '2,10,3,3', '--out', str(without)])
        check('the same answers build with the extra question', a.returncode == 0)
        check('and without it, the spare answer being harmless', b.returncode == 0)
        if a.returncode == 0:
            check('declining leaves the kext out',
                  not (with_drive / 'OC' / 'Kexts' / 'NVMeFix.kext').exists())
        short = run([sys.executable, 'tools/setup.py', '--machine', fixture,
                     '--nvme', 'Samsung SSD 970 EVO',
                     '--answers', '2,10,3', '--out', str(Path(tmp) / 'short' / 'EFI')],
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
    nvidia = {'generation': 'raptor-lake', 'laptop': False, 'pci_ids': [],
              'gpu_devices': [{'id': '10de:1187', 'name': 'GTX 760'}]}
    # the family rule used to need the word "nvidia" in the reported name, so a
    # card the machine called anything else came out unknown
    graphics = [r for r in summary.rows(nvidia) if r['part'] == 'Graphics']
    check('a card is judged on its vendor id, not on what it happens to be called',
          graphics and graphics[0]['verdict'] == summary.UNSUPPORTED, graphics)
    check('a long verdict wraps instead of losing its caveat',
          any('Turing' in l for l in summary.render(nvidia)))


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
          "acpi.run(Path(a.out).parent / 'acpi', tables)" in flow)

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

    # the tool must not take the builder down with it whatever it does
    src = Path('tools/acpi.py').read_text()
    check('and nothing the tool throws is left to reach the builder',
          'except BaseException' in src)


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
                 '--answers', '1,1,1', '--out', str(out)])
        check('a build with kexts added succeeds', r.returncode == 0)
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
    check('and with nothing capped, there is no ceiling', ceiling is None, ceiling)

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
    check('the range reaches the screen', 'Sierra 10.12 or newer' in rendered)
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
    check('the areas with no source are named as such',
          {r['area'] for r in table if r['kind'] == prov.NONE} ==
          {'Camera', 'AMD graphics kexts'},
          [r['area'] for r in table if r['kind'] == prov.NONE])
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
                     '--answers', '2,10,3', '--out', str(console)])
        check('the console still builds', typed.returncode == 0)

        # answered by name rather than by number, which is the point of the
        # event: a front end draws the rows and never has to count them
        want = {'What kind of machine is this?': 'laptop',
                'Which CPU generation?': 'kaby-lake',
                'Board or laptop brand?': 'hp'}
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
        check('the front end was asked the same three questions', len(asked) == 3, asked)
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
        pci, usb, hda, roles = detect.macos_devices()
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

    # the floor and ceiling turn into releases people know by name
    made = summary.genuine_mac({'board_id': silicon[0]['board']})
    check('a listed board comes back with a named release',
          made['listed'] and made['from']['name'], made)
    check('a machine with no board is not a Mac',
          summary.genuine_mac({}) is None)
    check('and a board nothing lists says so rather than nothing',
          summary.genuine_mac({'board_id': 'nope'}) == {
              'board': 'nope', 'from': None, 'to': None, 'listed': False})

    # this machine, if it happens to be one
    board = detect.probe().get('board_id')
    if board:
        check('this Mac names its own board', board and ' ' not in board, board)
        check('and the table has something to say about it',
              mactable.window(board) is not None, board)


if __name__ == '__main__':
    for section in (graphics, graphics_advice, audio_advice, storage, peripherals,
                    trackpad, framebuffer, boot_args, other_machine,
                    undecodable_output, scripted_answers, hardware_summary,
                    device_names, broadcom_wifi, detection_gaps, provenance,
                    framebuffers, native_device_ids, field_reports, load_order,
                    smbus_trackpad, macos_window, card_readers, third_party,
                    usb_mapping, acpi_tables, unattended_ssdts, ssdt_flow, window_stays_open,
                    frozen_names, frozen_build, workflow_flags,
                    runner_independence, tables_match_sources,
                    front_end_protocol, machine_document, machine_name,
                    embedded_fonts, macos_registry, genuine_macs):
        print(f'\n{section.__name__}')
        section()
    print()
    if FAILED:
        sys.exit(f'{len(FAILED)} failed: {", ".join(FAILED)}')
    print('  all good')
