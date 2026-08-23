// Opens one window, waits for it to settle, and reports its own memory.
//
// Self-reporting rather than measuring from outside: the number then means the
// same thing on both platforms, and it survives a headless runner where the
// window manager is xvfb.
using System;
using System.Diagnostics;
using System.IO;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Themes.Fluent;
using Avalonia.Threading;

namespace Bench;

static class Program
{
    static void Main(string[] args) => AppBuilder.Configure<Shell>()
        .UsePlatformDetect()
        .StartWithClassicDesktopLifetime(args);
}

class Shell : Application
{
    public override void Initialize() => Styles.Add(new FluentTheme());

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            desktop.MainWindow = new Window
            {
                Title = "Hackintosh EFI Builder",
                Width = 900,
                Height = 600,
                Content = new StackPanel
                {
                    Margin = new Thickness(24),
                    Spacing = 12,
                    Children =
                    {
                        new TextBlock { Text = "Hackintosh EFI Builder", FontSize = 22, FontWeight = FontWeight.SemiBold },
                        new TextBlock { Text = "A window, a theme, and nothing else." },
                        new ProgressBar { Value = 40, Maximum = 100, HorizontalAlignment = HorizontalAlignment.Stretch },
                        new Button { Content = "Build" },
                    },
                },
            };

            // five seconds is past the first frame and past the theme load, so
            // the peak includes startup rather than catching it mid-flight
            DispatcherTimer.RunOnce(() => { Report(); desktop.Shutdown(); }, TimeSpan.FromSeconds(5));
        }
        base.OnFrameworkInitializationCompleted();
    }

    static void Report()
    {
        var me = Process.GetCurrentProcess();
        me.Refresh();
        var lines = new[]
        {
            $"peak_working_set_bytes={me.PeakWorkingSet64}",
            $"working_set_bytes={me.WorkingSet64}",
            $"managed_heap_bytes={GC.GetTotalMemory(false)}",
        };
        foreach (var line in lines) Console.WriteLine(line);
        var into = Environment.GetEnvironmentVariable("BENCH_OUT");
        if (!string.IsNullOrEmpty(into)) File.WriteAllLines(into, lines);
    }
}
