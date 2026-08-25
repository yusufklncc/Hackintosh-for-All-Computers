// Fill the machine screen from what the engine describes.
//
// Nothing is decided here. Every verdict, every kext and every macOS bound
// arrives already worked out; this turns it into rows. A second opinion formed
// in the window would be a second answer to a question that already has one.
using System;
using System.Collections.Generic;
using System.Linq;
using Avalonia.Controls;
using Avalonia.Media;
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
        // An exception in an async event handler goes nowhere: the pane stays
        // empty, the program keeps running, and there is nothing to read. That
        // is how this failed on a real machine.
        Loaded += async (_, _) =>
        {
            try { await Load(); }
            catch (Exception e) { NoMachine("This went wrong: " + e); }
        };
    }

    async System.Threading.Tasks.Task Load()
    {
        // Reading a machine takes as long as that machine takes, and on Windows
        // the hardware queries are tens of seconds. An empty table for half a
        // minute looks like a program that has failed, so it says what it is
        // doing before it starts doing it.
        Content.IsVisible = false;
        Note("READING THIS MACHINE",
             "Asking the system what it has. On Windows this takes a few tens of "
             + "seconds the first time, because the hardware queries are slow.");

        var engine = Builder.Find(out var missing);
        if (engine is null) { NoMachine(missing); return; }

        var (machine, complaint) = await Builder.Describe(engine, Program.MachineFile);
        if (machine is null) { NoMachine(complaint); return; }
        // A Mac gets the note and the table both: the table is what it has,
        // and the note is why none of it is claimed here. Hiding the table
        // because nothing matched threw away the answer to "what is in it".
        Show(machine);
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
            // what the SUPPORT column means changes on a Mac, and saying so is
            // the difference between a table of verdicts and a table of them
            // about the wrong question
            var driven = machine.Rows.Count(r => r.Verdict == "driven by macOS");
            Note("THIS IS A MAC",
                 $"{machine.Profile.Model ?? "A Mac"}, so the question is not which "
                 + "kext would claim each device - none of them would - but which "
                 + $"driver macOS has given it. {driven} of these were read from the "
                 + $"running system, along with {ids} device ids. A Mac needs no EFI "
                 + "from this program: take a Report on the machine you are "
                 + "converting, or open the Builder with its report.");
        }
        else if (!machine.WorthShowing)
        {
            NoMachine("Nothing on this machine could be read.");
        }
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
        Content.IsVisible = true;
        Trouble.IsVisible = false;
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

        var counts = new[] { ("supported", "supported"),
                             ("driven by macOS", "driven by macOS"),
                             ("not supported", "not supported"),
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
            var last = m.Mac.To;
            Window.Text = last is null ? $"{shipped} and newer" : $"{shipped} to {last}";
            WindowWhy.Text = last is null
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

        if (m.Oclp.Count > 0)
        {
            var said = m.Oclp.Select(p => $"{p.What} from macOS {p.From}"
                                        + (p.To is { } to ? $" to {to}" : ""));
            Patched.Text = "Past that: OpenCore Legacy Patcher restores "
                         + string.Join(", ", said)
                         + ". Those patches go on an installed macOS, not in the "
                         + "EFI this builds, and OCLP is written for real Macs.";
            Patched.IsVisible = true;
        }
        else
        {
            Patched.IsVisible = false;
        }

        if (m.Graphics is { } advice)
        {
            GraphicsWarning.Text = advice.Text;
            GraphicsWarning.IsVisible = true;
            GraphicsWarning.Foreground = (IBrush?)(
                this.TryFindResource(advice.Tone == "unknown" ? "Warn" : "Bad",
                                     out var brush) ? brush : null);
        }
        else
        {
            GraphicsWarning.IsVisible = false;
        }

        if (m.Mac is null)
            Bounds.ItemsSource = m.Macos.Parts.Select(b => new BoundView(b)).ToList();
        Rows.ItemsSource =
            m.Rows.Select(r => new RowView(r)).ToList();
    }
}
