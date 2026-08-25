// What the program is, counted from the tree rather than remembered.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Shell.Engine;

namespace Shell.Views;

public sealed record CountItem(string Name, string Value);

public sealed class ToolItem
{
    public ToolItem(ToolRow row)
    {
        Path = row.Path;
        Upstream = row.Upstream ?? "no upstream recorded";
        Licence = row.Licence ?? "unread";
        Note = row.Note ?? "";
        HasNote = Note.Length > 0;
    }

    public string Path { get; }
    public string Upstream { get; }
    public string Licence { get; }
    public string Note { get; }
    public bool HasNote { get; }
}

public sealed class SourceItem
{
    public SourceItem(SourceRow row)
    {
        Area = row.Area;
        Kind = row.Kind;
        Source = row.Source;
        Covers = $"{row.Count} · {row.Covers}";
        Gap = row.Gap;
        HasGap = row.Gap.Length > 0;
        // derived beats quoted beats reported, and "none" is the one worth
        // colouring like a problem, because it is one
        IsDerived = row.Kind is "derived" or "measured";
        IsWeak = row.Kind is "quoted" or "reported";
        IsNone = row.Kind == "none";
    }

    public string Area { get; }
    public string Kind { get; }
    public string Source { get; }
    public string Covers { get; }
    public string Gap { get; }
    public bool HasGap { get; }
    public bool IsDerived { get; }
    public bool IsWeak { get; }
    public bool IsNone { get; }
}

public partial class AboutView : UserControl
{
    bool _loaded;

    public AboutView() => InitializeComponent();

    public async Task Load()
    {
        if (_loaded) return;
        _loaded = true;
        var engine = Builder.Find(out var missing);
        if (engine is null) { Tally.Text = missing; return; }

        var (about, complaint) = await Inventory.Facts(engine);
        if (about is null) { Tally.Text = complaint; return; }

        Counts.ItemsSource = new List<CountItem>
        {
            new("OPENCORE", about.OpenCore ?? "unknown"),
            new("CONFIGS", about.Configs.ToString()),
            new("KEXTS", about.Kexts.ToString()),
            new("SOURCES", about.Sources.Count.ToString()),
            new("NETWORK", about.Offline ? "never" : "sometimes"),
        };

        // counted, not asserted. It used to say "both ACPI tools" while nine
        // programs travelled in the package.
        Offline.Text = "Nothing here reaches the network while it runs. The machine "
                     + "an EFI is prepared on is usually the machine about to be "
                     + $"replaced, and it is often not online - so {about.Kexts} kexts, "
                     + $"{about.Configs} configs and {about.Tools.Count} whole programs "
                     + "travel inside it. The tables below were fetched once, by the "
                     + "tool named beside each, and committed.";
        Licence.Text = (about.Licence is { } licence ? licence + ". " : "")
                     + (about.Repo ?? "");
        Tools.ItemsSource = about.Tools.Select(t => new ToolItem(t)).ToList();

        // the order is the order of how much a claim is worth
        var order = new[] { "derived", "measured", "quoted", "reported", "none" };
        var said = order.Where(k => about.Tally.ContainsKey(k))
                        .Select(k => $"{about.Tally[k]} {k}");
        Tally.Text = $"{string.Join(", ", said)}. Derived means it was read out of the "
                   + "thing itself - a kext's own matching rules, the profile tree. "
                   + "Quoted means a sentence from a document. Reported means somebody "
                   + "ran it and said what happened. None means this repository has no "
                   + "source for it and says so rather than guessing.";
        // weakest first. A page whose subject is where the answers come from
        // should open on the ones that came from nowhere, not bury them at
        // twenty-two of twenty-six.
        var weight = new Dictionary<string, int>
        {
            ["none"] = 0, ["reported"] = 1, ["quoted"] = 2,
            ["measured"] = 3, ["derived"] = 4,
        };
        Sources.ItemsSource = about.Sources
            .OrderBy(s => weight.GetValueOrDefault(s.Kind, 9))
            .ThenBy(s => s.Area, StringComparer.OrdinalIgnoreCase)
            .Select(s => new SourceItem(s)).ToList();
    }
}
