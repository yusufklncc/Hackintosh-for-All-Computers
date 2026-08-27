---
title: Building for another machine
---

# Building for another machine

Detection reads the computer it runs on. If you are preparing the USB on a
working PC for a different one, everything it finds - graphics, audio codec,
network cards, NVMe, trackpad - belongs to the wrong machine, and you do not
want any of it in the config.

## With a hardware report

The fix is to take the report on the target machine and carry it over.

1. On the machine you are building **for**, run the program and open the
   **Report** pane. It writes one small JSON file: CPU, board, graphics, PCI,
   USB and audio ids, NVMe models.

    The Builder's fourth answer, *Neither - just write this machine's report*,
    does the same thing.

2. Copy that file to the computer you are building **on** - by USB stick, mail,
   anything. It holds no serial numbers and no raw device dump.

3. There, start the Builder and answer *Another machine, and I have its hardware
   report*. It asks for the file.

Every question and every piece of advice then applies to that machine.

## Without one

Answer *Another machine, and I do not have one*. Nothing is detected and nothing
is guessed at; instead you are asked which Ethernet, Wi-Fi and Bluetooth it has,
by name, from the drivers this repository ships.

!!! warning "What a name cannot tell it"
    Graphics, audio and the trackpad need the report. They cannot be worked out
    from a model name, and the builder will not pretend otherwise.
