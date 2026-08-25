using System.Threading.Tasks;
using Avalonia.Controls;
using Shell.Engine;

namespace Shell.Views;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        foreach (var nav in new[] { ToMachine, ToBuilder, ToReport, ToRecovery,
                                    ToDevices, ToKexts, ToAbout })
            nav.IsCheckedChanged += async (_, _) => await Swap();
        _ = Standing();
    }

    /// <summary>The numbers under the nav, read from the tree rather than typed here.
    ///
    /// They were typed here once - "OpenCore 1.0.6", "41 kexts" - and the tree
    /// said 1.0.5 and 42. A number nobody can check is a number nobody should
    /// believe.</summary>
    async Task Standing()
    {
        var engine = Builder.Find(out _);
        if (engine is null) return;
        var (about, _) = await Inventory.Facts(engine);
        if (about is null) return;
        Version.Text = about.OpenCore is { } v ? $"OpenCore {v}" : "OpenCore, version unread";
        StandingFacts.Text = $"{about.Configs} configs\n{about.Kexts} kexts vendored\n"
                           + (about.Offline ? "no network to build" : "");
    }

    /// <summary>Switch panes, and let the one being shown read what it needs.</summary>
    async Task Swap()
    {
        MachinePane.IsVisible = ToMachine.IsChecked == true;
        BuilderPane.IsVisible = ToBuilder.IsChecked == true;
        ReportPane.IsVisible = ToReport.IsChecked == true;
        RecoveryPane.IsVisible = ToRecovery.IsChecked == true;
        DevicesPane.IsVisible = ToDevices.IsChecked == true;
        KextsPane.IsVisible = ToKexts.IsChecked == true;
        AboutPane.IsVisible = ToAbout.IsChecked == true;
        // read on first sight rather than at startup: opening the program
        // should not wait on three documents nobody has asked for yet
        if (ToRecovery.IsChecked == true) await RecoveryPane.Load();
        if (ToDevices.IsChecked == true) await DevicesPane.Load();
        if (ToKexts.IsChecked == true) await KextsPane.Load();
        if (ToAbout.IsChecked == true) await AboutPane.Load();
    }

    /// <summary>Switch to the builder and start one, for the screenshot pass.</summary>
    public async Task ShowBuilder()
    {
        ToBuilder.IsChecked = true;
        await BuilderPane.StartForRender();
    }

    public string BuilderState() => BuilderPane.State();

    public Task<string> TakeReport() => ReportPane.TakeForRender();

    public Task<string> ListRecoveries() => RecoveryPane.ListForRender();

    public Task<string> DriveBuilder() => BuilderPane.DriveToEnd();

    /// <summary>Show one pane by name, for the screenshot pass.</summary>
    public async Task Show(string pane)
    {
        var nav = pane switch
        {
            "report" => ToReport, "recovery" => ToRecovery,
            "devices" => ToDevices, "kexts" => ToKexts,
            "about" => ToAbout,
            "builder" => ToBuilder, _ => ToMachine,
        };
        nav.IsChecked = true;
        await Swap();
    }
}
