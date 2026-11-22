using System;
using System.Linq;
using Avalonia;

namespace Shell;

static class Program
{
    /// <summary>Where to write a picture of the window instead of waiting for somebody.
    ///
    /// The window is the deliverable, and nobody can review a window from a
    /// build log. This renders it to a file so a change to the layout can be
    /// looked at the same way a change to the code is read.</summary>
    public static string? RenderTo;

    /// <summary>A hardware report to show instead of this machine.
    ///
    /// The same thing --machine does for the console: the EFI is usually
    /// prepared on a computer that is not the target, so the screen has to be
    /// able to show a machine that is somewhere else.</summary>
    public static string? MachineFile;

    [STAThread]
    public static int Main(string[] args)
    {
        // what this build is and what an update would replace, for CI to read
        // without opening a window
        if (args.Contains("--build-info"))
        {
            var (asset, target, why) = Shell.Engine.Updater.Plan();
            Console.WriteLine($"commit {Shell.Engine.Updater.Commit ?? "unknown"}");
            Console.WriteLine($"built {Shell.Engine.Updater.Built?.ToString("o") ?? "unknown"}");
            Console.WriteLine($"asset {asset ?? "none"}  target {target ?? why}");
            return 0;
        }
        // the whole update without a window: check, download, verify, swap.
        // What the About pane's button does, for testing it end to end.
        if (args.Contains("--update-now"))
        {
            var (newer, said) = Shell.Engine.Updater.Check().GetAwaiter().GetResult();
            Console.WriteLine(said);
            if (newer is null) return 1;
            var (script, complaint) = Shell.Engine.Updater.Stage(newer, (_, _) => { })
                .GetAwaiter().GetResult();
            if (script is null) { Console.WriteLine(complaint); return 1; }
            Console.WriteLine(Shell.Engine.Updater.Launch(script) ? $"swapping: {script}" : "could not start the swap");
            return 0;
        }
        for (var i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == "--render") RenderTo = args[i + 1];
            if (args[i] == "--machine") MachineFile = args[i + 1];
        }
        BuildAvaloniaApp().StartWithClassicDesktopLifetime(args);
        return 0;
    }

    public static AppBuilder BuildAvaloniaApp() => AppBuilder.Configure<App>()
        .UsePlatformDetect()
        // The two faces are embedded as resources, so the window looks the
        // same on a machine with no fonts installed as on one with all of
        // them - and a runner rendering a screenshot is the machine with none.
        .LogToTrace();
}
