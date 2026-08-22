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
          {'Camera', 'Card reader', 'USB port mapping', 'AMD graphics kexts'},
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


if __name__ == '__main__':
    for section in (graphics, graphics_advice, audio_advice, storage, peripherals,
                    trackpad, framebuffer, boot_args, other_machine, undecodable_output, scripted_answers,
                    hardware_summary, device_names, broadcom_wifi,
                    detection_gaps, provenance, framebuffers, native_device_ids, field_reports, macos_window,
                    tables_match_sources):
        print(f'\n{section.__name__}')
        section()
    print()
    if FAILED:
        sys.exit(f'{len(FAILED)} failed: {", ".join(FAILED)}')
    print('  all good')
