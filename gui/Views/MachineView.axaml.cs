// Fill the machine screen from what the engine describes.
//
// Nothing is decided here. Every verdict, every kext and every macOS bound
// arrives already worked out; this turns it into rows. A second opinion formed
// in the window would be a second answer to a question that already has one.
using System;
using System.Collections.Generic;
using System.Linq;
using Avalonia.Controls;
using Avalonia.Markup.Xaml;
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
        AvaloniaXamlLoader.Load(this);
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
            // a Mac reports none of its own hardware to these queries, and
            // eight rows of "unknown" is not a report
            NoMachine("Nothing on this machine could be read. That is what a Mac " +
                    "looks like here: it reports its hardware in a way these " +
                    "queries do not reach.");
            return;
        }
        Show(machine);
    }

    // named for what it says, not for the panel it says it in: the generated
    // field for that panel is already called Trouble
    void NoMachine(string why)
    {
        Trouble.IsVisible = true;
        TroubleText.Text = why;
    }

    void Show(MachineDocument m)
    {
        Source.Text =
            m.Source.StartsWith("report", StringComparison.Ordinal)
                ? "READ FROM " + m.Source.ToUpperInvariant()
                : "READ FROM THIS MACHINE";

        // the processor is the only name this program can honestly give a
        // machine: nothing here reads a model from the firmware
        MachineName.Text =
            m.Profile.Cpu ?? "Unnamed machine";

        var spec = new List<SpecView>();
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
