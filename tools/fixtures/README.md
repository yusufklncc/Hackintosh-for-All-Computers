# Fixtures

`no-hardware.json` is a hardware report describing nothing at all.

It exists because a test that detects the machine it runs on is a test whose
questions change with the machine. A CI runner that happens to have an NVMe
drive is asked one more question than one that does not, so a fixed `--answers`
string builds a different EFI on the two - or runs out and fails on one of them,
which is exactly what happened and read as a flaky job for a while.

Passing `--machine tools/fixtures/no-hardware.json` starts from nothing, and
`--ids`, `--usb-ids`, `--hda-ids` and `--nvme` then put in exactly the hardware
a test is about. Nothing else can appear.

It is not for building an EFI with. A build from it has no advice in it, because
there is nothing to advise on.
