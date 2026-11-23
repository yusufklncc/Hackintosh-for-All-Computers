// Fill the machine screen from what the engine describes.
//
// Nothing is decided here. Every verdict, every kext and every macOS bound
// arrives already worked out; this turns it into rows. A second opinion formed
// in the window would be a second answer to a question that already has one.
using System;
using System.Collections.Generic;
using System.Linq;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Layout;
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
        IsUnknown = verdict is "unknown" or "third-party driver";
    }

    public string Text { get; }
    public bool IsOk { get; }
    public bool IsBad { get; }
    public bool IsUnknown { get; }
}

public partial class MachineView : UserControl
{
    // the releases the strips run across, oldest to newest darwin
    (int lo, int hi) _scale = (14, 25);

    IBrush? Brush(string key) =>
        this.TryFindResource(key, ActualThemeVariant, out var b) ? b as IBrush : null;

    /// <summary>One part's span of macOS: its name, whether it sets an end of
    /// the machine's range, a strip with the span filled in, and the span in
    /// words underneath.</summary>
    Control RangeRow(string what, Release? from, Release? to, string sets)
    {
        var (lo, hi) = _scale;
        var start = Math.Clamp(from?.Darwin ?? lo, lo, hi);
        var end = Math.Clamp((to?.Darwin ?? hi) + 1, start + 1, hi + 1);
        var marks = sets.Length > 0;

        var head = new Grid { ColumnDefinitions = new ColumnDefinitions("*,Auto"), ColumnSpacing = 8 };
        head.Children.Add(new TextBlock
        {
            Text = what, FontSize = 13, Foreground = Brush("Ink"),
            FontWeight = marks ? FontWeight.SemiBold : FontWeight.Normal,
            TextTrimming = TextTrimming.CharacterEllipsis,
        });
        if (marks)
        {
            var tag = new Border
            {
                CornerRadius = new CornerRadius(8), Padding = new Thickness(7, 1, 7, 2),
                Background = Brush("AccentSoft"), VerticalAlignment = VerticalAlignment.Center,
                Child = new TextBlock { Text = sets, FontSize = 10.5, FontWeight = FontWeight.SemiBold,
                                        Foreground = Brush("Accent") },
            };
            Grid.SetColumn(tag, 1);
            head.Children.Add(tag);
        }

        // the strip: what comes before the span, the span, what comes after
        var strip = new Grid
        {
            Height = 6, Margin = new Thickness(0, 6, 0, 4),
            ColumnDefinitions = new ColumnDefinitions(
                $"{Math.Max(start - lo, 0.0001)}*,{end - start}*,{Math.Max(hi + 1 - end, 0.0001)}*"),
        };
        strip.Children.Add(new Border
        {
            CornerRadius = new CornerRadius(3), Background = Brush("Chrome"),
            [Grid.ColumnSpanProperty] = 3,
        });
        var span = new Border
        {
            CornerRadius = new CornerRadius(3),
            Background = marks ? Brush("Accent") : Brush("Muted"),
            Opacity = marks ? 1 : 0.45,
        };
        Grid.SetColumn(span, 1);
        strip.Children.Add(span);

        var words = new TextBlock
        {
            Classes = { "mono" }, FontSize = 11.5,
            Text = $"{(from is null ? "any" : from.ToString())}  →  {(to is null ? "current" : to.ToString())}",
        };
        var row = new StackPanel { Spacing = 0 };
        row.Children.Add(head);
        row.Children.Add(strip);
        row.Children.Add(words);
        return row;
    }

    /// <summary>A list that is not a range - the lines Apple still updates -
    /// as one chip each, so it cannot be read as a span.</summary>
    Control ChipRow(string what, IEnumerable<string> values)
    {
        var row = new StackPanel { Spacing = 6 };
        row.Children.Add(new TextBlock { Text = what, FontSize = 13, Foreground = Brush("Ink") });
        var chips = new WrapPanel();
        foreach (var v in values)
            chips.Children.Add(new Border
            {
                CornerRadius = new CornerRadius(6), Padding = new Thickness(8, 2, 8, 3),
                Margin = new Thickness(0, 0, 6, 6), BorderThickness = new Thickness(1),
                BorderBrush = Brush("Line"), Background = Brush("Surface2"),
                Child = new TextBlock { Text = v, Classes = { "mono" }, Foreground = Brush("Ink") },
            });
        row.Children.Add(chips);
        return row;
    }

    /// <summary>Raised by the button that goes on to the EFI pane.</summary>
    public event Action? BuildRequested;

    /// <summary>Raised when a machine has been read and drawn.</summary>
    public event Action? Read;

    public MachineView()
    {
        // InitializeComponent, not AvaloniaXamlLoader.Load: the generated
        // method loads the XAML *and* assigns the named controls. Calling the
        // loader on its own leaves every one of them null, and the first line
        // that touches one is where it shows.
        InitializeComponent();
        BuildForIt.Click += (_, _) => BuildRequested?.Invoke();
        // An exception in an async event handler goes nowhere: the pane stays
        // empty, the program keeps running, and there is nothing to read. That
        // is how this failed on a real machine.
        Loaded += async (_, _) =>
        {
            try { await Load(); }
            catch (Exception e) { NoMachine("This went wrong: " + e); }
        };
    }

    /// <summary>Read the machine again: after a report was opened, or closed.</summary>
    public System.Threading.Tasks.Task Reload() => Load();

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

        Reading.Say(Program.MachineFile is null ? "Reading this machine…" : "Reading the report…");
        var (machine, complaint) = await Builder.Describe(engine, Program.MachineFile);
        Reading.Say(null);
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
                 + "from this program: save a report on the machine you are "
                 + "converting, and open it below.");
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
        // the drawing follows what the machine is, not what most of them are
        Tower.IsVisible = m.Platform == "desktop";
        Silhouette.IsVisible = !Tower.IsVisible;
        if (m.Profile.Oem is { } oem) spec.Add(new SpecView("board", oem));
        Spec.ItemsSource = spec;

        var counts = new[] { ("supported", "supported"),
                             ("driven by macOS", "driven by macOS"),
                             ("not supported", "not supported"),
                             ("third-party driver", "third-party driver"),
                             ("unknown", "unknown"), ("-", "not present") };
        Tally.ItemsSource = counts
            .Select(c => (verdict: c.Item1, label: c.Item2,
                          n: m.Rows.Count(r => r.Verdict == c.Item1)))
            .Where(c => c.n > 0)
            .Select(c => new TallyView(c.n, c.label, c.verdict))
            .ToList();

        // A real Mac's answer comes from Apple, not from the kext tables: they
        // claim none of its hardware, so they have nothing to say about it.
        if (m.Mac is { Listed: true })
        {
            var last = m.Mac.To;
            // the board list recovery images are fetched by names Intel Macs
            // only, so an Apple silicon Mac has no ceiling here at all - only
            // Apple's update metadata, which is a different fact
            var unread = !m.Mac.Current && last is null;
            Window.Text = m.Mac.Current ? "Whatever Apple is serving now"
                        : unread ? "Not read here"
                        : $"Up to {last}";
            WindowWhy.Text = m.Mac.Current
                ? $"{m.Mac.Board} is one of the boards Apple keeps current, so "
                + "this Mac is offered the newest macOS there is."
                : unread
                ? $"{m.Mac.Board} is not in the board list recovery images are fetched "
                + "by, which names Intel Macs only, so how far it goes is not read here."
                : $"{m.Mac.Board} is offered up to {last}. There is no floor "
                + "here: nothing this reads knows the oldest macOS a Mac runs.";
            Bounds.Children.Clear();
            if (!unread)
                Bounds.Children.Add(RangeRow("Apple, for " + m.Mac.Board, null, m.Mac.To,
                                             m.Mac.To is null ? "" : "sets the newest"));
            // a different fact, and it used to be read as the one above:
            // which lines Apple still publishes for it is about updates
            if (m.Mac.Serving.Count > 0)
                Bounds.Children.Add(ChipRow("Apple still updates it on", m.Mac.Serving));
        }
        else if (m.Mac is { Listed: false })
        {
            Window.Text = "Not in Apple's list";
            WindowWhy.Text = $"{m.Mac.Board} is not in any macOS line Apple still "
                           + "serves, which happens to a Mac too old for all of them.";
            Bounds.Children.Clear();
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
                                     ActualThemeVariant, out var brush) ? brush : null);
        }
        else
        {
            GraphicsWarning.IsVisible = false;
        }

        // a Mac read as itself needs no EFI; anything else, a report of one
        // included, is something the EFI pane can build for
        BuildForIt.IsVisible = m.Mac is null;
        Read?.Invoke();
        if (m.Mac is null)
        {
            Bounds.Children.Clear();
            _scale = (Math.Min(14, m.Macos.Parts.Select(b => b.From?.Darwin ?? 99).DefaultIfEmpty(99).Min()),
                      Math.Max(25, m.Macos.Parts.Select(b => b.To?.Darwin ?? 0).DefaultIfEmpty(0).Max()));
            foreach (var b in m.Macos.Parts)
            {
                var floor = b.From is not null && b.What == m.Macos.FromBecause;
                var ceiling = b.To is not null && b.What == m.Macos.ToBecause;
                Bounds.Children.Add(RangeRow(b.What, b.From, b.To,
                    floor && ceiling ? "sets both ends" : floor ? "sets the oldest"
                    : ceiling ? "sets the newest" : ""));
            }
        }
        // an empty panel read as one that had not loaded
        NoBounds.IsVisible = Bounds.Children.Count == 0;
        Rows.ItemsSource =
            m.Rows.Select(r => new RowView(r)).ToList();
    }
}
