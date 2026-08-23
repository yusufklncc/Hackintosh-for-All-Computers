// Fill the machine screen from what the engine describes.
//
// Nothing is decided here. Every verdict, every kext and every macOS bound
// arrives already worked out; this turns it into rows. A second opinion formed
// in the window would be a second answer to a question that already has one.
using System;
using System.Collections.Generic;
using System.Linq;
using Avalonia.Controls;
using Shell;
using Shell.Engine;

namespace Shell.Views;

public sealed record SpecView(string Name, string Value);

public sealed class TallyView
{
    public TallyView(int count, string label, string verdict)
    {
        Text = $"{count} {label}";
        IsOk = verdict == "supported";
        IsBad = verdict == "not supported";
        IsUnknown = verdict == "unknown";
    }

    public string Text { get; }
    public bool IsOk { get; }
    public bool IsBad { get; }
    public bool IsUnknown { get; }
}

public partial class MachineView : UserControl
{
    public MachineView()
    {
        // InitializeComponent, not AvaloniaXamlLoader.Load: the generated
        // method loads the XAML *and* assigns the named controls. Calling the
        // loader on its own leaves every one of them null, and the first line
        // that touches one is where it shows.
        InitializeComponent();
        Loaded += async (_, _) => await Load();
    }

    async System.Threading.Tasks.Task Load()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null) { NoMachine(missing); return; }

        var (machine, complaint) = await Builder.Describe(engine, Program.MachineFile);
        if (machine is null) { NoMachine(complaint); return; }
        if (!machine.WorthShowing)
        {
            // Read and unmatched is not the same as unreadable, and on a Mac
            // it is the ordinary case: the hardware is Apple's and nothing
            // this ships claims any of it.
            // from the probe, not from the rows: a row that recognised nothing
            // carries no id, and summing those said nothing was readable on a
            // machine five devices had just been read from
            var ids = machine.Read.GetValueOrDefault("pci")
                    + machine.Read.GetValueOrDefault("usb");
            NoMachine(machine.Profile.System == "Darwin"
                ? $"This is a {machine.Profile.Model ?? "Mac"}. " +
                  (ids > 0
                      ? $"{ids} device ids were read from it and nothing here claims "
                      + "any of them, which is what a Mac looks like - its hardware "
                      + "is Apple's."
                      : "Nothing was readable on it.") +
                  " It needs no EFI from this program: take a Report on the machine " +
                  "you are converting, or open the Builder with its report."
                : "Nothing on this machine could be read.");
            return;
        }
        Show(machine);
    }

    // named for what it says, not for the panel it says it in: the generated
    // field for that panel is already called Trouble
    void NoMachine(string why)
    {
        // the empty table underneath is not a table of nothing, it is furniture
        Content.IsVisible = false;
        Trouble.IsVisible = true;
        TroubleText.Text = why;
    }

    void Show(MachineDocument m)
    {
        Source.Text =
            m.Source.StartsWith("report", StringComparison.Ordinal)
                ? "READ FROM " + m.Source.ToUpperInvariant()
                : "READ FROM THIS MACHINE";

        // the name the machine gives itself, where it gives one. Vendors leave
        // that field at a placeholder often enough that the engine filters it,
        // and then the processor is the only honest name left.
        MachineName.Text = m.Profile.Model ?? m.Profile.Cpu ?? "Unnamed machine";

        var spec = new List<SpecView>();
        if (m.Profile.Model is not null && m.Profile.Cpu is { } cpu)
            spec.Add(new SpecView("", cpu));
        if (m.Profile.Generation is { } gen) spec.Add(new SpecView("generation", gen));
        if (m.Profile.Cores is { } cores) spec.Add(new SpecView("cores", cores.ToString()));
        if (m.Platform is { } platform) spec.Add(new SpecView("form factor", platform));
        if (m.Profile.Oem is { } oem) spec.Add(new SpecView("board", oem));
        Spec.ItemsSource = spec;

        var counts = new[] { ("supported", "supported"), ("not supported", "not supported"),
                             ("unknown", "unknown"), ("-", "not present") };
        Tally.ItemsSource = counts
            .Select(c => (verdict: c.Item1, label: c.Item2,
                          n: m.Rows.Count(r => r.Verdict == c.Item1)))
            .Where(c => c.n > 0)
            .Select(c => new TallyView(c.n, c.label, c.verdict))
            .ToList();

        if (m.Macos.From is { } from)
        {
            Window.Text = m.Macos.To is { } to ? $"{from} – {to}" : $"{from} and newer";
            WindowWhy.Text = m.Macos.To is not null
                ? $"floor set by {m.Macos.FromBecause}; ceiling by {m.Macos.ToBecause}"
                : $"floor set by {m.Macos.FromBecause}. No part here sets a ceiling - " +
                  "the SMBIOS a build picks has one of its own.";
        }
        else
        {
            Window.Text = "Not bounded here";
            WindowWhy.Text = "Nothing on this machine narrows the range, which is not the " +
                       "same as saying every release works.";
        }

        Bounds.ItemsSource =
            m.Macos.Parts.Select(b => new BoundView(b)).ToList();
        Rows.ItemsSource =
            m.Rows.Select(r => new RowView(r)).ToList();
    }
}
