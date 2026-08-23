// Finding the engine and asking it something.
//
// The engine is the program that already exists: one executable beside this
// one when both are installed, and tools/setup.py from a clone when somebody
// is working on it. Nothing here reimplements any part of it - if this cannot
// find it, it says so rather than filling the window with what it guessed.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace Shell.Engine;

public sealed record Located(string Program, IReadOnlyList<string> Prefix, string Where);

public static class Builder
{
    static readonly string ExeName =
        OperatingSystem.IsWindows() ? "HackintoshEFIBuilder.exe" : "HackintoshEFIBuilder";

    /// <summary>Where the engine is, or null with a sentence saying where it was looked for.</summary>
    public static Located? Find(out string complaint)
    {
        var beside = AppContext.BaseDirectory;
        var packaged = Path.Combine(beside, ExeName);
        if (File.Exists(packaged))
        {
            complaint = "";
            return new Located(packaged, Array.Empty<string>(), "beside this window");
        }

        // a clone: walk up for the tools directory rather than assuming how
        // deep the build output happens to be
        for (var dir = new DirectoryInfo(beside); dir is not null; dir = dir.Parent)
        {
            var script = Path.Combine(dir.FullName, "tools", "setup.py");
            if (!File.Exists(script)) continue;
            var python = Interpreter();
            if (python is null)
            {
                complaint = "Found the engine at " + script + " but no Python that " +
                            "can run it. It needs 3.11 or newer, for tomllib.";
                return null;
            }
            complaint = "";
            return new Located(python, new[] { script }, "a clone at " + dir.FullName);
        }

        complaint = $"No engine found. Looked for {ExeName} beside this window, " +
                    $"and for tools/setup.py above {beside}.";
        return null;
    }

    static string? _python;

    /// <summary>A Python that can actually run the engine, or null.
    ///
    /// "python3" is not enough. Launched from a file manager the search path is
    /// the bare system one, and on macOS that is Python 3.9 - which has no
    /// tomllib, so every table the engine reads fails to load. The same launch
    /// from a terminal works, which is the worst way for this to be wrong.</summary>
    static string? Interpreter()
    {
        if (_python is not null) return _python;
        var candidates = OperatingSystem.IsWindows()
            ? new[] { "python", "py" }
            : new[]
            {
                "python3.13", "python3.12", "python3.11", "python3",
                // a file manager launch does not have these on the path
                "/opt/homebrew/bin/python3", "/usr/local/bin/python3",
            };
        foreach (var candidate in candidates.Concat(FromLoginShell()))
        {
            try
            {
                using var probe = Process.Start(new ProcessStartInfo
                {
                    FileName = candidate,
                    ArgumentList = { "-c", "import tomllib" },
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                });
                if (probe is null) continue;
                probe.WaitForExit(5000);
                if (probe.HasExited && probe.ExitCode == 0) return _python = candidate;
            }
            catch (Exception e) when (e is System.ComponentModel.Win32Exception or IOException)
            {
                // not installed under that name, which is the common case for
                // most of this list
            }
        }
        return null;
    }

    /// <summary>Whatever the person's own shell calls python3, if anything.
    ///
    /// Version managers - mise, pyenv, asdf - put their interpreter on a path
    /// that only exists once a login shell has run its profile. A window
    /// started from a file manager never runs one, so the interpreter is there
    /// and unreachable. Asking the shell is the only way to find out where.</summary>
    static IEnumerable<string> FromLoginShell()
    {
        if (OperatingSystem.IsWindows()) yield break;
        var shell = Environment.GetEnvironmentVariable("SHELL");
        if (string.IsNullOrEmpty(shell) || !File.Exists(shell)) yield break;
        // -lic before -lc. A login shell reads .zprofile; the version managers
        // put their activation in .zshrc, which only an interactive shell
        // reads. Measured on a machine with mise: -lc answered /usr/bin/python3
        // (3.9, no tomllib) and -lic answered the 3.12 that actually works.
        foreach (var how in new[] { "-lic", "-lc" })
        {
            string found;
            try
            {
                using var ask = Process.Start(new ProcessStartInfo
                {
                    FileName = shell,
                    ArgumentList = { how, "command -v python3" },
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                });
                if (ask is null) continue;
                found = ask.StandardOutput.ReadToEnd();
                ask.WaitForExit(15000);
                if (!ask.HasExited) continue;
            }
            catch (Exception e) when (e is System.ComponentModel.Win32Exception or IOException)
            {
                continue;
            }
            // the last line: an interactive profile printing a banner, or a
            // warning on the way through, is normal
            var last = found.Split('\n', StringSplitOptions.RemoveEmptyEntries)
                            .LastOrDefault()?.Trim();
            if (!string.IsNullOrEmpty(last) && File.Exists(last)) yield return last;
        }
    }

    /// <summary>Run the engine once and hand back what it wrote to stdout.</summary>
    public static async Task<(string output, string error, int code)> Run(
        Located engine, params string[] arguments)
    {
        var info = new ProcessStartInfo
        {
            FileName = engine.Program,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            // and stdin, closed immediately. Without this the engine inherits
            // whatever this window has, which when it was double-clicked is a
            // handle nobody can read from - and a program that decides to wait
            // on it waits for ever, printing nothing.
            RedirectStandardInput = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        foreach (var a in engine.Prefix) info.ArgumentList.Add(a);
        foreach (var a in arguments) info.ArgumentList.Add(a);
        // the engine reads its own tables from beside itself; a clone needs the
        // repository root as the working directory or none of them are found
        var root = engine.Prefix.Count > 0
            ? Directory.GetParent(Path.GetDirectoryName(engine.Prefix[0])!)!.FullName
            : Path.GetDirectoryName(engine.Program)!;
        info.WorkingDirectory = root;

        using var process = new Process { StartInfo = info };
        process.Start();
        process.StandardInput.Close();
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        // Bounded. Reading a machine is slow, not endless, and a window that
        // waits for ever on one tells nobody anything.
        var exited = process.WaitForExitAsync();
        var finished = await Task.WhenAny(exited, Task.Delay(TimeSpan.FromMinutes(3)));
        if (finished != exited)
        {
            try { process.Kill(entireProcessTree: true); } catch (Exception) { }
            return ("", $"{Path.GetFileName(engine.Program)} did not answer within "
                      + "three minutes, so it was stopped.", 1);
        }
        return (await stdout, await stderr, process.ExitCode);
    }

    /// <summary>The machine, as the engine describes it.</summary>
    public static async Task<(MachineDocument? machine, string complaint)> Describe(
        Located engine, string? report = null)
    {
        var arguments = report is null
            ? new[] { "--describe" }
            : new[] { "--describe", "--machine", report };
        var (output, error, code) = await Run(engine, arguments);
        if (code != 0)
            return (null, error.Trim() is { Length: > 0 } said ? said
                                                              : $"the engine exited {code}");
        try
        {
            var doc = JsonSerializer.Deserialize(output, Payload.Default.MachineDocument);
            return doc is null ? (null, "the engine wrote nothing") : (doc, "");
        }
        catch (JsonException e)
        {
            return (null, "could not read what the engine wrote: " + e.Message);
        }
    }
}
