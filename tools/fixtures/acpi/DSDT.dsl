DefinitionBlock ("", "DSDT", 2, "TEST", "TESTDSDT", 0x00000001)
{
    Scope (\_SB)
    {
        Device (PCI0)
        {
            Name (_HID, EisaId ("PNP0A08"))
            Name (_ADR, Zero)
            Device (LPCB)
            {
                Name (_ADR, 0x001F0000)
                Device (EC)
                {
                    Name (_HID, EisaId ("PNP0C09"))
                    Method (_STA, 0, NotSerialized) { Return (0x0F) }
                }
                Device (RTC)
                {
                    Name (_HID, EisaId ("PNP0B00"))
                    Name (_CRS, ResourceTemplate () { IO (Decode16, 0x0070, 0x0070, 0x01, 0x08) })
                }
                Device (HPET)
                {
                    Name (_HID, EisaId ("PNP0103"))
                    Name (_CRS, ResourceTemplate () { IRQNoFlags () {0,8,11} })
                }
            }
            Device (SBUS) { Name (_ADR, 0x001F0004) }
        }
        Processor (CPU0, 0x00, 0x00000410, 0x06) {}
        Processor (CPU1, 0x01, 0x00000410, 0x06) {}
    }
}
