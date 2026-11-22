// The kexts this program can put in an EFI, and where each came from.
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Shell.Engine;

namespace Shell.Views;

public sealed class KextItem
{
    /// <summary>A heading row: the group the kexts under it are filed in.</summary>
    public KextItem(string group, int count)
    {
        IsHeader = true;
        Heading = $"{group.ToUpperInvariant()}  ·  {count}";
    }

    public KextItem(KextRow row)
    {
        IsRow = true;
        Bundle = row.Bundle;
        Upstream = row.Upstream ?? "no upstream recorded";
        Version = row.Version ?? "—";
        // "none stated" is the absence of a licence, not a permissive one, and
        // the table says so in the same words the licence file does
        Licence = row.Licence ?? "unread";
        // marked, because either one means nobody has granted anything
        LicenceUnclear = Licence is "unread" or "none stated";
        // The table is generated from what each kext binds to by device id.
        // AppleALC matches on a layout, Lilu on nothing at all - neither is
        // idle, and neither has a row, so this says what is true of both.
        Drives = row.Label ?? "";
        // what it is for, in its project's words, where nothing claims a
        // device for it - AppleALC matches a codec layout, Lilu nothing
        Said = row.Said.Length == 0 ? ""
             : (row.SaidOfProject ? "Its project: " : "") + $"\u201c{row.Said}\u201d";
        HasSaid = Said.Length > 0 && (row.Label is null);
        if (row.Label is null && Said.Length == 0) Drives = "nothing it says about itself is recorded";
        Devices = row.Devices == 1 ? "1 device id" : $"{row.Devices} device ids";
        HasDevices = row.Devices > 0;
    }

    public bool IsHeader { get; }
    public bool IsRow { get; }
    public string Heading { get; } = "";
    public bool LicenceUnclear { get; }
    public string Said { get; } = "";
    public bool HasSaid { get; }
    public string Bundle { get; } = "";
    public string Upstream { get; } = "";
    public string Version { get; } = "";
    public string Licence { get; } = "";
    public string Drives { get; } = "";
    public string Devices { get; } = "";
    public bool HasDevices { get; }
}

public partial class KextsView : UserControl
{
    Task? _loaded;

    public KextsView()
    {
        InitializeComponent();
    }

    /// <summary>Read the list the first time this pane is looked at.</summary>
    // One read, and everybody waits for the same one. A bool guard let the
    // second caller past while the first was still awaiting: the nav's own
    // handler starts a Swap of its own, so two arrive together, and the second
    // returned to a pane that had not been filled yet. The screenshot pass
    // caught it on an empty list.
    public Task Load()
    {
        // and a read that threw is not a read: keeping the faulted task would
        // make every later look at this pane raise the same old exception
        if (_loaded is { IsFaulted: true }) _loaded = null;
        return _loaded ??= Fill();
    }

    async Task Fill()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null) { Blurb.Text = missing; return; }

        Reading.Say("Reading the kexts…");
        var (list, complaint) = await Inventory.Kexts(engine);
        Reading.Say(null);
        if (list is null) { Blurb.Text = complaint; return; }

        var claiming = list.Kexts.Count(k => k.Devices > 0);
        var ids = list.Kexts.Sum(k => k.Devices);
        Blurb.Text = $"{list.Kexts.Count} kexts travel inside this program, so a build " +
                     $"never reaches the network. {claiming} of them claim {ids} device " +
                     "ids between them, read out of the kexts themselves rather than " +
                     "from a list somebody kept.";
        // in the engine's order, which is by group, each group under its name
        var rows = new System.Collections.Generic.List<KextItem>();
        foreach (var g in list.Kexts.GroupBy(k => k.Group))
        {
            rows.Add(new KextItem(g.Key, g.Count()));
            rows.AddRange(g.Select(k => new KextItem(k)));
        }
        Rows.ItemsSource = rows;
    }
}
