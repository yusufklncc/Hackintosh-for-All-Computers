// What the program is, counted from the tree rather than remembered.
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Shell.Engine;

namespace Shell.Views;

public sealed record CountItem(string Name, string Value);

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
            new("NETWORK", about.Offline ? "never" : "sometimes"),
        };

        // the order is the order of how much a claim is worth
        var order = new[] { "derived", "measured", "quoted", "reported", "none" };
        var said = order.Where(k => about.Tally.ContainsKey(k))
                        .Select(k => $"{about.Tally[k]} {k}");
        Tally.Text = $"{string.Join(", ", said)}. Derived means it was read out of the "
                   + "thing itself - a kext's own matching rules, the profile tree. "
                   + "Quoted means a sentence from a document. Reported means somebody "
                   + "ran it and said what happened. None means this repository has no "
                   + "source for it and says so rather than guessing.";
        Sources.ItemsSource = about.Sources.Select(s => new SourceItem(s)).ToList();
    }
}
