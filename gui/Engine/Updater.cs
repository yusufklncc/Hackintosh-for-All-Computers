// Keeping the window and its engine current, from inside the window.
//
// A release here keeps its number while its packages are rebuilt - v1.0.8 is
// OpenCore 1.0.8, however many times it is republished - so "is there an
// update" cannot be answered by comparing numbers. It is answered by the
// commit a package was built from: the release carries update.json, naming
// its commit, when it was built, and the SHA-256 of every file, and this
// build carries its own commit and build time in its assembly metadata.
//
// Installing is the program's own: the package is downloaded by this process,
// so no quarantine mark is put on it and the first-run warnings do not come
// back. It is refused unless its hash is the one update.json names. The swap
// happens after the window has closed, by a short script it leaves behind,
// and it replaces the two programs only - an EFI, a report or anything else a
// person made beside them stays where it is.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;

namespace Shell.Engine;

public sealed class UpdateAsset
{
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("sha256")] public string Sha256 { get; set; } = "";
    [JsonPropertyName("size")] public long Size { get; set; }
}

public sealed class UpdateInfo
{
    [JsonPropertyName("tag")] public string Tag { get; set; } = "";
    [JsonPropertyName("commit")] public string Commit { get; set; } = "";
    [JsonPropertyName("built")] public string Built { get; set; } = "";
    [JsonPropertyName("summary")] public List<string> Summary { get; set; } = new();
    [JsonPropertyName("assets")] public List<UpdateAsset> Assets { get; set; } = new();
}

public sealed class UpdateSettings
{
    [JsonPropertyName("check_at_start")] public bool CheckAtStart { get; set; } = true;
}

[JsonSerializable(typeof(UpdateInfo))]
[JsonSerializable(typeof(UpdateSettings))]
public partial class UpdateJson : JsonSerializerContext
{
}

public static class Updater
{
    const string Repo = "yusufklncc/Hackintosh-for-All-Computers";
    public const string ReleasePage = $"https://github.com/{Repo}/releases/latest";
    // "latest" follows whichever tag is newest, so a v1.0.9 is found by a
    // window built as v1.0.8 without anything here naming it
    const string Manifest = $"https://github.com/{Repo}/releases/latest/download/update.json";
    // for testing the whole loop against a local server; nobody else sets it
    static readonly string? Base = Environment.GetEnvironmentVariable("HACKINTOSH_UPDATE_BASE");
    static string ManifestUrl => Base is null ? Manifest : $"{Base}/update.json";
    static string AssetUrl(string tag, string asset) => Base is null
        ? $"https://github.com/{Repo}/releases/download/{tag}/{asset}" : $"{Base}/{asset}";

    static string? Metadata(string key) =>
        Assembly.GetEntryAssembly()?.GetCustomAttributes<AssemblyMetadataAttribute>()
            .FirstOrDefault(a => a.Key == key)?.Value;

    /// <summary>The commit this window was built from, or null for a build
    /// that does not know - then nothing is offered, because "newer" cannot be
    /// told from "different".</summary>
    public static string? Commit
    {
        get
        {
            var version = Assembly.GetEntryAssembly()?
                .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion;
            var plus = version?.IndexOf('+') ?? -1;
            return plus >= 0 && version!.Length > plus + 7 ? version[(plus + 1)..] : null;
        }
    }

    public static DateTimeOffset? Built =>
        DateTimeOffset.TryParse(Metadata("BuildTime"), out var at) ? at : null;

    /// <summary>A sentence for the About pane: what this build is.</summary>
    public static string Describe() => Commit is { } c
        ? $"This build: {c[..Math.Min(7, c.Length)]}"
          + (Built is { } b ? $", built {b.UtcDateTime:yyyy-MM-dd HH:mm} UTC" : "")
        : "This build does not know which commit it came from, so it cannot tell a newer one.";

    // --- settings -----------------------------------------------------------

    static string SettingsFile => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "Hackintosh EFI Builder", "settings.json");

    public static UpdateSettings Settings
    {
        get
        {
            try
            {
                return JsonSerializer.Deserialize(File.ReadAllText(SettingsFile),
                                                  UpdateJson.Default.UpdateSettings) ?? new();
            }
            catch (Exception) { return new(); }
        }
        set
        {
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(SettingsFile)!);
                File.WriteAllText(SettingsFile, JsonSerializer.Serialize(value, UpdateJson.Default.UpdateSettings));
            }
            catch (Exception) { /* a setting that cannot be saved is one that resets */ }
        }
    }

    // --- checking -----------------------------------------------------------

    static readonly HttpClient Http = new() { Timeout = TimeSpan.FromSeconds(20) };

    static Updater()
    {
        Http.DefaultRequestHeaders.UserAgent.ParseAdd("HackintoshEFIBuilder-updater");
    }

    /// <summary>(newer release or null, what was found). Never throws.</summary>
    public static async Task<(UpdateInfo? newer, string said)> Check()
    {
        if (Commit is null) return (null, Describe());
        UpdateInfo? info;
        try
        {
            var text = await Http.GetStringAsync(ManifestUrl);
            info = JsonSerializer.Deserialize(text, UpdateJson.Default.UpdateInfo);
        }
        catch (Exception e)
        {
            return (null, $"Could not ask GitHub: {e.Message}");
        }
        if (info is null || info.Commit.Length == 0)
            return (null, "The release names no commit, so there is nothing to compare.");
        return Newer(info, Commit, Built)
            ? (info, $"{info.Tag} has a newer build: {info.Commit[..7]}.")
            : (null, $"Up to date: {info.Tag}, built from {info.Commit[..7]}.");
    }

    /// <summary>Whether a release is newer than this build. Different is not
    /// enough: a window built from a later commit than the release must not
    /// be offered the release as an update.</summary>
    public static bool Newer(UpdateInfo info, string? commit, DateTimeOffset? built)
    {
        if (commit is null || info.Commit.Length == 0) return false;
        if (commit.StartsWith(info.Commit, StringComparison.OrdinalIgnoreCase)
            || info.Commit.StartsWith(commit, StringComparison.OrdinalIgnoreCase))
            return false;
        if (built is null || !DateTimeOffset.TryParse(info.Built, out var released)) return true;
        return released > built.Value;
    }

    // --- installing ---------------------------------------------------------

    /// <summary>The release file this system takes, and where it goes.</summary>
    public static (string? asset, string? target, string why) Plan()
    {
        var rid = RuntimeInformation.RuntimeIdentifier;
        if (OperatingSystem.IsMacOS())
        {
            var bundle = Places.Bundle;
            return bundle is null
                ? (null, null, "This is not running from a .app, so there is nothing to replace.")
                : ($"HackintoshEFIBuilder-{rid}.zip", bundle, "");
        }
        if (OperatingSystem.IsLinux() && Environment.GetEnvironmentVariable("APPIMAGE") is { } image)
            return ($"HackintoshEFIBuilder-{rid}.AppImage", image, "");
        return ($"HackintoshEFIBuilder-{rid}.zip", AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar), "");
    }

    static bool Writable(string target)
    {
        var folder = File.Exists(target) ? Path.GetDirectoryName(target)! : Path.GetDirectoryName(target.TrimEnd('/'))!;
        try
        {
            var probe = Path.Combine(folder, $".update-probe-{Environment.ProcessId}");
            File.WriteAllText(probe, "");
            File.Delete(probe);
            return true;
        }
        catch (Exception) { return false; }
    }

    /// <summary>Download, check and stage an update. Returns (script to run
    /// after the window closes, complaint). progress gets (bytes, total).</summary>
    public static async Task<(string? script, string complaint)> Stage(
        UpdateInfo info, Action<long, long> progress, CancellationToken stop = default)
    {
        var (asset, target, why) = Plan();
        if (asset is null || target is null) return (null, why);
        var listed = info.Assets.FirstOrDefault(a => a.Name == asset);
        if (listed is null) return (null, $"The release has no {asset} for this system.");
        if (!Writable(target))
            return (null, "This program sits somewhere it cannot write to, so it cannot replace "
                        + "itself. The release page has the new package.");

        var work = Path.Combine(Path.GetTempPath(), $"hackintosh-update-{Environment.ProcessId}");
        if (Directory.Exists(work)) Directory.Delete(work, true);
        Directory.CreateDirectory(work);
        var file = Path.Combine(work, asset);
        try
        {
            using var response = await Http.GetAsync(
                AssetUrl(info.Tag, asset),
                HttpCompletionOption.ResponseHeadersRead, stop);
            response.EnsureSuccessStatusCode();
            var total = response.Content.Headers.ContentLength ?? listed.Size;
            await using var from = await response.Content.ReadAsStreamAsync(stop);
            await using var to = File.Create(file);
            var buffer = new byte[1 << 20];
            long done = 0;
            int n;
            while ((n = await from.ReadAsync(buffer, stop)) > 0)
            {
                await to.WriteAsync(buffer.AsMemory(0, n), stop);
                done += n;
                progress(done, total);
            }
        }
        catch (Exception e)
        {
            return (null, $"The download stopped: {e.Message}");
        }

        await using (var check = File.OpenRead(file))
        {
            var got = Convert.ToHexString(await SHA256.HashDataAsync(check, stop)).ToLowerInvariant();
            if (got != listed.Sha256.ToLowerInvariant())
                return (null, $"{asset} is not the file the release lists (expected "
                            + $"{listed.Sha256[..12]}, got {got[..12]}); nothing was changed.");
        }

        try
        {
            return (Script(file, target, work), "");
        }
        catch (Exception e)
        {
            return (null, $"The new package could not be unpacked: {e.Message}");
        }
    }

    /// <summary>Unpack the package and write the script that swaps it in once
    /// this process has gone. Only the programs are replaced.</summary>
    static string Script(string package, string target, string work)
    {
        var pid = Environment.ProcessId;
        var unpacked = Path.Combine(work, "new");
        if (OperatingSystem.IsWindows())
        {
            System.IO.Compression.ZipFile.ExtractToDirectory(package, unpacked);
            var script = Path.Combine(work, "update.ps1");
            File.WriteAllText(script, $$"""
                $ErrorActionPreference = 'Stop'
                while (Get-Process -Id {{pid}} -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 300 }
                $target = '{{target.Replace("'", "''")}}'
                $new = '{{unpacked.Replace("'", "''")}}'
                # the engine's folder is replaced whole, so nothing of the old
                # one is left behind; the window is one file
                if (Test-Path "$target\EFIBuilderEngine") { Remove-Item "$target\EFIBuilderEngine" -Recurse -Force }
                Copy-Item "$new\EFIBuilderEngine" "$target\EFIBuilderEngine" -Recurse -Force
                Copy-Item "$new\HackintoshEFIBuilder.exe" "$target\HackintoshEFIBuilder.exe" -Force
                Start-Process "$target\HackintoshEFIBuilder.exe"
                """);
            return script;
        }
        if (OperatingSystem.IsMacOS())
        {
            Directory.CreateDirectory(unpacked);
            // ditto, as the package was made with: a zip library drops the
            // symlinks inside the engine's Python.framework, and the bundle's
            // signature with them
            using (var p = Process.Start("ditto", new[] { "-x", "-k", package, unpacked }))
            {
                p!.WaitForExit();
                if (p.ExitCode != 0) throw new IOException("ditto could not unpack it");
            }
            var app = Directory.GetDirectories(unpacked, "*.app").FirstOrDefault()
                      ?? throw new IOException("no .app in the package");
            var script = Path.Combine(work, "update.sh");
            File.WriteAllText(script, $"""
                #!/bin/sh
                while kill -0 {pid} 2>/dev/null; do sleep 0.3; done
                rm -rf "{target}"
                ditto "{app}" "{target}"
                open "{target}"
                """);
            return script;
        }
        // Linux: the AppImage is one file; the folder package is the two programs
        if (package.EndsWith(".AppImage", StringComparison.Ordinal))
        {
            var script = Path.Combine(work, "update.sh");
            File.WriteAllText(script, $"""
                #!/bin/sh
                while kill -0 {pid} 2>/dev/null; do sleep 0.3; done
                mv -f "{package}" "{target}"
                chmod +x "{target}"
                "{target}" >/dev/null 2>&1 &
                """);
            return script;
        }
        Directory.CreateDirectory(unpacked);
        using (var p = Process.Start("unzip", new[] { "-q", package, "-d", unpacked }))
        {
            p!.WaitForExit();
            if (p.ExitCode != 0) throw new IOException("unzip could not unpack it");
        }
        var sh = Path.Combine(work, "update.sh");
        File.WriteAllText(sh, $"""
            #!/bin/sh
            while kill -0 {pid} 2>/dev/null; do sleep 0.3; done
            rm -rf "{target}/EFIBuilderEngine"
            cp -R "{unpacked}/EFIBuilderEngine" "{target}/EFIBuilderEngine"
            cp -f "{unpacked}/HackintoshEFIBuilder" "{target}/HackintoshEFIBuilder"
            "{target}/HackintoshEFIBuilder" >/dev/null 2>&1 &
            """);
        return sh;
    }

    /// <summary>Start the swap script on its own, before the window quits.</summary>
    public static bool Launch(string script)
    {
        try
        {
            var info = OperatingSystem.IsWindows()
                ? new ProcessStartInfo("powershell",
                    new[] { "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", script })
                : new ProcessStartInfo("/bin/sh", new[] { script });
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            return Process.Start(info) is not null;
        }
        catch (Exception) { return false; }
    }
}
