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
        // A Mac gets the note and the table both: the table is what it has,
        // and the note is why none of it is claimed here. Hiding the table
        // because nothing matched threw away the answer to "what is in it".
        if (machine.Profile.System == "Darwin")
        {
            // Read and unmatched is not the same as unreadable, and on a Mac
            // it is the ordinary case: the hardware is Apple's and nothing
            // this ships claims any of it.
            // from the probe, not from the rows: a row that recognised nothing
            // carries no id, and summing those said nothing was readable on a
            // machine five devices had just been read from
            var ids = machine.Read.GetValueOrDefault("pci")
                    + machine.Read.GetValueOrDefault("usb");
            Note("THIS IS A MAC",
                 $"{machine.Profile.Model ?? "A Mac"}, and its hardware is Apple's - "
                 + $"{ids} device ids were read and nothing here claims them, which is "
                 + "the expected answer. A Mac needs no EFI from this program. Take a "
                 + "Report on the machine you are converting, or open the Builder with "
                 + "its report.");
        }
        else if (!machine.WorthShowing)
        {
            NoMachine("Nothing on this machine could be read.");
            return;
        }
        Show(machine);
    }

    // named for what it says, not for the panel it says it in: the generated
    // field for that panel is already called Trouble
    /// <summary>Something to say about the whole table, above it.</summary>
    void Note(string title, string text)
    {
        Trouble.IsVisible = true;
        TroubleTitle.Text = title;
        TroubleText.Text = text;
    }

    void NoMachine(string why)
    {
        // the empty table underneath is not a table of nothing, it is furniture
        Content.IsVisible = false;
        Note("NO MACHINE TO SHOW", why);
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

        // A real Mac's answer comes from Apple, not from the kext tables: they
        // claim none of its hardware, so they have nothing to say about it.
        if (m.Mac is { Listed: true, From: { } shipped })
        {
            Window.Text = m.Mac.To is { } last
                ? $"{shipped} to {last}"
                : $"{shipped} and newer";
            WindowWhy.Text = m.Mac.To is null
                ? $"Apple still lists {m.Mac.Board} in the newest macOS it serves, "
                + "so this Mac is supported."
                : $"Apple no longer lists {m.Mac.Board} past {last}.";
            Bounds.ItemsSource = new List<BoundView>
            {
                new(new Bound { What = "Apple, for " + m.Mac.Board,
                                From = m.Mac.From, To = m.Mac.To }),
            };
        }
        else if (m.Mac is { Listed: false })
        {
            Window.Text = "Not in Apple's list";
            WindowWhy.Text = $"{m.Mac.Board} is not in any macOS line Apple still "
                           + "serves, which happens to a Mac too old for all of them.";
            Bounds.ItemsSource = new List<BoundView>();
        }
        else if (m.Macos.From is { } from)
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

        if (m.Mac is null)
            Bounds.ItemsSource = m.Macos.Parts.Select(b => new BoundView(b)).ToList();
        Rows.ItemsSource =
            m.Rows.Select(r => new RowView(r)).ToList();
    }
}
