using System;
using System.Threading.Tasks;
using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using Avalonia.Styling;
using Avalonia.Threading;
using Shell.Views;

namespace Shell;

public partial class App : Application
{
    public override void Initialize() => AvaloniaXamlLoader.Load(this);

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            var window = new MainWindow();
            desktop.MainWindow = window;
            if (Program.RenderTo is { } into)
                // long enough for the engine to answer and the first frame to
                // settle; a picture taken mid-layout is a picture of nothing
                DispatcherTimer.RunOnce(() => Capture(window, into, desktop),
                                        TimeSpan.FromSeconds(8));
        }
        base.OnFrameworkInitializationCompleted();
    }

    void Capture(MainWindow window, string into,
                 IClassicDesktopStyleApplicationLifetime desktop)
    {
        ReportTypefaces();
        var engine = Shell.Engine.Builder.Find(out var missing);
        Console.WriteLine("engine: " + (engine?.Where ?? "not found - " + missing));
        // both themes, because both are shipped and only one of them is the one
        // being looked at when a colour is chosen
        Save(window, into);
        RequestedThemeVariant = ThemeVariant.Dark;
        DispatcherTimer.RunOnce(() =>
        {
            Save(window, into.Replace(".png", "-dark.png", StringComparison.Ordinal));
            RequestedThemeVariant = ThemeVariant.Light;
            // and the other pane, with an engine actually running in it: a
            // picture of an empty transcript would prove nothing
            _ = window.ShowBuilder();
            // waited for rather than timed: probing a machine takes as long as
            // that machine takes, and on Windows that is a good deal longer
            // than a number picked here would have guessed
            WhenAsked(window, async () =>
            {
                Console.WriteLine(window.BuilderState());
                Save(window, into.Replace(".png", "-builder.png", StringComparison.Ordinal));
                // and then all the way through, answering the way the machine
                // suggests. A pane that draws the first question and cannot
                // finish a build has not been tested, only photographed.
                try
                {
                    Console.WriteLine("drive: " + await window.DriveBuilder());
                    foreach (var pane in new[] { "report", "kexts", "about" })
                    {
                        await window.Show(pane);
                        // the report pane's whole job is behind a button, so
                        // the pass presses it rather than photographing it idle
                        if (pane == "report")
                            Console.WriteLine("report: " + await window.TakeReport());
                        // one turn of the loop, so what was just loaded is laid
                        // out before its picture is taken
                        await Task.Delay(1200);
                        Save(window, into.Replace(".png", $"-{pane}.png",
                                                  StringComparison.Ordinal));
                    }
                }
                catch (Exception e)
                {
                    // an unobserved exception here is a hang, not a failure,
                    // and a hang tells a build log nothing at all
                    Console.WriteLine("drive: threw " + e);
                }
                desktop.Shutdown();
            });
        }, TimeSpan.FromSeconds(2));
    }

    /// <summary>Say which faces actually got used.
    ///
    /// A font that failed to load falls back to whatever the system has, and
    /// the window still looks reasonable - which is the problem. This prints
    /// what was resolved so a build can fail on it instead of a person
    /// squinting at a screenshot.</summary>
    void ReportTypefaces()
    {
        foreach (var (key, weight) in new[]
                 {
                     ("Sans", FontWeight.Normal), ("Sans", FontWeight.SemiBold),
                     ("Mono", FontWeight.Normal),
                 })
        {
            var family = (FontFamily)Resources[key]!;
            var found = FontManager.Current.TryGetGlyphTypeface(
                new Typeface(family, FontStyle.Normal, weight), out var face);
            // numbers on both sides: the enum prints 600 as "DemiBold", which
            // is a name for the weight and not the one that was asked for
            Console.WriteLine($"typeface {key}/{(int)weight} -> " +
                              (found ? $"{face!.FamilyName} {(int)face.Weight}"
                                     : "NOT FOUND"));
        }
    }

    /// <summary>Run this once the builder has a question up, or give up.</summary>
    static void WhenAsked(MainWindow window, Func<Task> then, int secondsLeft = 90)
    {
        DispatcherTimer.RunOnce(() =>
        {
            if (secondsLeft <= 0 || window.BuilderState().Contains("asking"))
                _ = then();
            else
                WhenAsked(window, then, secondsLeft - 1);
        }, TimeSpan.FromSeconds(1));
    }

    static void Save(MainWindow window, string into)
    {
        var size = new PixelSize(Math.Max(1, (int)window.ClientSize.Width),
                                 Math.Max(1, (int)window.ClientSize.Height));
        using var bitmap = new RenderTargetBitmap(size, new Vector(96, 96));
        bitmap.Render(window);
        bitmap.Save(into);
        Console.WriteLine($"wrote {into} at {size.Width}x{size.Height}");
    }
}
