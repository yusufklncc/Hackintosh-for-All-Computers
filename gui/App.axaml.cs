using System;
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
        // both themes, because both are shipped and only one of them is the one
        // being looked at when a colour is chosen
        Save(window, into);
        RequestedThemeVariant = ThemeVariant.Dark;
        DispatcherTimer.RunOnce(() =>
        {
            Save(window, into.Replace(".png", "-dark.png", StringComparison.Ordinal));
            desktop.Shutdown();
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
