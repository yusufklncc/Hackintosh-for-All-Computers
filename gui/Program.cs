using System;
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
        // embedded rather than asked for: a runner has almost no fonts, and a
        // window whose text silently fell back is not the window being reviewed
        .WithInterFont()
        .LogToTrace();
}
