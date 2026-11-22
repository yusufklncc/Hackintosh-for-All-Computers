// Where this program puts what it makes for a person.
//
// Beside the program, where it can be: a folder unzipped from a release is the
// person's own, and they expect the EFI next to the executable they ran. Not
// inside a .app: the bundle is replaced whole by an update, macOS may be
// running it from a read-only copy (App Translocation), and an EFI written
// into Contents/MacOS is lost the first time either happens.
using System;
using System.IO;

namespace Shell.Engine;

public static class Places
{
    /// <summary>The .app this runs from, or null when it is not in one.</summary>
    public static string? Bundle
    {
        get
        {
            var dir = new DirectoryInfo(AppContext.BaseDirectory);
            for (var d = dir; d is not null; d = d.Parent)
                if (d.Name.EndsWith(".app", StringComparison.OrdinalIgnoreCase))
                    return d.FullName;
            return null;
        }
    }

    /// <summary>The folder an EFI, a report or a recovery goes in by default.</summary>
    public static string Work
    {
        get
        {
            if (Bundle is null) return AppContext.BaseDirectory;
            var documents = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
            var folder = Path.Combine(documents, "Hackintosh EFI Builder");
            try { Directory.CreateDirectory(folder); }
            catch (Exception) { return documents; }
            return folder;
        }
    }
}
