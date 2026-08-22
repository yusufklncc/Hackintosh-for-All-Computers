# A DSDT to run the patches against

`DSDT.dsl` is written here and `DSDT.aml` is what the vendored `iasl` makes of
it. It is not a dump of any machine: it is the smallest table that has the
things the automatic patches look for - an EC with a `_STA`, a PNP0B00 RTC, a
HPET with conflicting IRQs, an SMBus device and two Processor objects.

It exists so the unattended path can be tested on every platform rather than
only on a machine that can dump its own tables. Compiling it again from the
`.dsl` is one command:

    vendor/tools/iasl/<platform>/iasl DSDT.dsl

The HPET IRQs are deliberately in conflict. That is what makes `fix_hpet` ask a
question, which is what proves the guard refuses to answer for somebody.
