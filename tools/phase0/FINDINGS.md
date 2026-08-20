# Phase 0 findings

Analysis of the 178 configs under `EFI/OC/config/`, run with the scripts in this
directory. Question: can these be generated from layered profiles instead of
maintained by hand?

Answer: yes. The tree is already layered, the layers are just materialised.

## Layer coordinates

Every config decomposes into `platform / vendor / cpu [+ chipset] [+ oem] [+ variant]`,
derived from its path and filename:

| axis     | values                                                        |
|----------|---------------------------------------------------------------|
| platform | desktop (117), laptop (61)                                     |
| vendor   | intel (82), amd (35), n/a for laptop (61)                      |
| cpu      | 31 distinct generations                                        |
| chipset  | 9 (b450-x470-x570, b550-a520, trx40, z370, z390, h61.., h77.., hm67.., hm77..) |
| oem      | hp (41), dell-sony (28), dell (13), sony (13), asus (4), msi (1) |
| variant  | bios-v3006 (1)                                                 |

46 configs are canonical (no overlay); the other 132 are overlay variants.

## Overlay consistency

Each overlay must produce the same delta everywhere it applies, or it is not a
real layer. Excluding generated identity fields (serial / MLB / UUID) and
cosmetic `Comment` strings:

    20 consistent, 4 inconsistent

The load-bearing overlays are clean and tiny:

| overlay              | configs | delta                                                    |
|----------------------|---------|----------------------------------------------------------|
| oem:hp               | 35      | `Kernel.Quirks.LapicKernelPanic`, `UEFI.Quirks.UnblockFsConnect` |
| oem:dell-sony        | 22      | `Kernel.Quirks.CustomSMBIOSGuid`, `PlatformInfo.UpdateSMBIOSMode` |
| oem:dell             | 13      | same as dell-sony                                          |
| oem:sony             | 13      | same as dell-sony                                          |
| chipset:b450-x470-x570 | 8     | `Booter.Quirks.SetupVirtualMap`                            |
| chipset:b550-a520    | 8       | + `SSDT-CPUR.aml`                                          |
| chipset:trx40        | 8       | `DevirtualiseMmio`, `SetupVirtualMap`                      |

The 4 inconsistencies are not modelling failures:

* 3 of them trace to a single stray value. `Laptop/003` sets
  `SMCProcessor.kext MinKernel=8.0.0` where its three siblings use `11.0.0`.
  The kext is `Enabled=false` in all four, so there is no runtime effect - it is
  silent drift, exactly what a generator removes.
* 1 is `oem:asus`: its 3 configs have 3 genuinely different deltas and carry
  attribution comments from an unrelated project. Different provenance, so they
  belong as explicit per-config profiles, not as an `oem/asus` layer.

## Sizing

Across the 46 canonical configs (659 distinct key paths):

    LEVEL 0  base, identical everywhere          233 keys
    LEVEL 1  desktop/amd    (11 configs)         288 keys on top of base
             desktop/intel  (22 configs)          24 keys
             laptop         (13 configs)          97 keys
    LEVEL 2  cpu profile                     avg  12.9 keys (amd)
                                             avg  83.5 keys (intel desktop)
                                             avg  64.3 keys (laptop)

The Intel/laptop per-profile figures are inflated by treating `Kernel.Add` and
`ACPI.Add` as positional arrays. Modelling them as named lists - one line per
enabled entry, disabled entries simply absent - collapses them:

    positional arrays : 3755 keys
    named lists       :  416 lines   (89% smaller)

Enabled kexts per profile cluster tightly: 3, 4, 5, 6 or 13-14. That is a strong
signal for a small set of reusable named kext bundles rather than per-profile
lists.

## Conclusion

~35 profile files plus roughly 60 lines of overlay reproduce all 178 configs.
The named-list representation for `Kernel.Add` / `ACPI.Add` is the single
biggest lever on profile size and should be part of the schema from the start.

Nothing here should be deleted until a generator reproduces all 178 configs
semantically. That equivalence check is the gate for Phase 1.
