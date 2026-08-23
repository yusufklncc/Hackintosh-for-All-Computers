// Show a folder or a file where the person can see it.
//
// Every system has its own name for this and none of them is a shell command
// worth writing twice. A build that says where it went and cannot take you
// there is a path to copy by hand.
using System;
using System.Diagnostics;
using System.IO;

namespace Shell.Engine;

public static class Reveal
{
    /// <summary>Open a folder, or select a file inside its folder.</summary>
    public static bool Show(string path)
    {
        if (string.IsNullOrEmpty(path)) return false;
        var isFile = File.Exists(path);
        if (!isFile && !Directory.Exists(path)) return false;
        try
        {
            if (OperatingSystem.IsWindows())
                return Run("explorer.exe", isFile ? $"/select,\"{path}\"" : $"\"{path}\"");
            if (OperatingSystem.IsMacOS())
                return Run("open", isFile ? $"-R \"{path}\"" : $"\"{path}\"");
            // xdg-open takes a folder, so a file becomes the folder holding it
            var folder = isFile ? Path.GetDirectoryName(path)! : path;
            return Run("xdg-open", $"\"{folder}\"");
        }
        catch (Exception e) when (e is System.ComponentModel.Win32Exception or IOException)
        {
            return false;
        }
    }

    static bool Run(string program, string arguments)
    {
        using var started = Process.Start(new ProcessStartInfo
        {
            FileName = program, Arguments = arguments, UseShellExecute = false,
            CreateNoWindow = true,
        });
        return started is not null;
    }
}
