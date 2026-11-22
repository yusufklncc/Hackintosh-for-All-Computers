using System.Threading.Tasks;
using Avalonia.Controls;
using Shell.Engine;

namespace Shell.Views;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        foreach (var nav in new[] { ToMachine, ToBuilder, ToStick, ToDevices,
                                    ToKexts, ToAbout })
            nav.IsCheckedChanged += async (_, _) => await Swap();
        // a report opened on the Machine pane is the machine everything else is
        // about: the table, the builder's answers and the stick's advice
        ReportPart.Switched += async _ =>
        {
            await MachineInfo.Reload();
            await StickPane.MachineChanged();
        };
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
        StickPane.IsVisible = ToStick.IsChecked == true;
        DevicesPane.IsVisible = ToDevices.IsChecked == true;
        KextsPane.IsVisible = ToKexts.IsChecked == true;
        AboutPane.IsVisible = ToAbout.IsChecked == true;
        // read on first sight rather than at startup: opening the program
        // should not wait on three documents nobody has asked for yet
        if (ToStick.IsChecked == true) await StickPane.Load();
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

    public Task<string> TakeReport() => ReportPart.TakeForRender();

    public Task<string> ListRecoveries() => StickPane.ListRecoveries();

    public Task<string> ListSticks() => StickPane.ListSticks();
    public Task<string> InstallerState() => StickPane.InstallerState();

    public Task<string> DriveBuilder() => BuilderPane.DriveToEnd();

    /// <summary>Show one pane by name, for the screenshot pass.</summary>
    public async Task Show(string pane)
    {
        var nav = pane switch
        {
            // the parts that were panes of their own are shown where they live now
            "report" => ToMachine,
            "recovery" or "installer" or "stick" => ToStick,
            "devices" => ToDevices, "kexts" => ToKexts,
            "about" => ToAbout,
            "builder" => ToBuilder, _ => ToMachine,
        };
        nav.IsChecked = true;
        await Swap();
    }
}
