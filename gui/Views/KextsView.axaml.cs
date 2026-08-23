// The kexts this program can put in an EFI, and where each came from.
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Shell.Engine;

namespace Shell.Views;

public sealed class KextItem
{
    public KextItem(KextRow row)
    {
        Bundle = row.Bundle;
        Upstream = row.Upstream ?? "no upstream recorded";
        Version = row.Version ?? "—";
        // "none stated" is the absence of a licence, not a permissive one, and
        // the table says so in the same words the licence file does
        Licence = row.Licence ?? "unread";
        // The table is generated from what each kext binds to by device id.
        // AppleALC matches on a layout, Lilu on nothing at all - neither is
        // idle, and neither has a row, so this says what is true of both.
        Drives = row.Label ?? "not matched by device id";
        Devices = row.Devices == 1 ? "1 device id" : $"{row.Devices} device ids";
        HasDevices = row.Devices > 0;
    }

    public string Bundle { get; }
    public string Upstream { get; }
    public string Version { get; }
    public string Licence { get; }
    public string Drives { get; }
    public string Devices { get; }
    public bool HasDevices { get; }
}

public partial class KextsView : UserControl
{
    bool _loaded;

    public KextsView()
    {
        InitializeComponent();
    }

    /// <summary>Read the list the first time this pane is looked at.</summary>
    public async Task Load()
    {
        if (_loaded) return;
        _loaded = true;
        var engine = Builder.Find(out var missing);
        if (engine is null) { Blurb.Text = missing; return; }

        var (list, complaint) = await Inventory.Kexts(engine);
        if (list is null) { Blurb.Text = complaint; return; }

        var claiming = list.Kexts.Count(k => k.Devices > 0);
        var ids = list.Kexts.Sum(k => k.Devices);
        Blurb.Text = $"{list.Kexts.Count} kexts travel inside this program, so a build " +
                     $"never reaches the network. {claiming} of them claim {ids} device " +
                     "ids between them, read out of the kexts themselves rather than " +
                     "from a list somebody kept.";
        Rows.ItemsSource = list.Kexts.Select(k => new KextItem(k)).ToList();
    }
}
