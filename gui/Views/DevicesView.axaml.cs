// Everything the tables know, in one list a person can search.
//
// The rows are read once and filtered in memory. Six hundred of them is not a
// number worth asking the engine about again on every keystroke, and a
// catalogue that lags behind the typing is a catalogue nobody uses.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Shell.Engine;

namespace Shell.Views;

public sealed class DeviceItem
{
    public DeviceItem(DeviceRow row)
    {
        Category = row.Category;
        Name = row.Name;
        Vendor = Short(row.Vendor ?? "");
        Id = row.Id ?? "";
        Kext = row.Kext ?? "";
        HasKext = Kext.Length > 0;
        Note = row.Note;
        HasNote = Note.Length > 0;
        Status = row.Status;
        IsOk = row.Status == "supported";
        IsBad = row.Status == "unsupported";
        IsUnclear = row.Status is "untested" or "spoofed" or "dropped" or "third-party";
        // a range on each line: what macOS drove it, and where OCLP takes it
        var native = row.Macos is { From: { } from }
            ? from + (row.Macos.To is { } to ? $" – {to}" : " +") : "";
        var patched = row.Macos is { Oclp: { } oclp }
            ? "OCLP " + oclp + (row.Macos.OclpTo is { } until ? $" – {until}" : "+")
            : "";
        Macos = string.Join("\n", new[] { native, patched }.Where(x => x.Length > 0));
        // a dash rather than an empty cell: no range recorded is a fact about
        // the row, and a blank column read as one that had failed to load
        if (Macos.Length == 0) Macos = "\u2014";
        // one string to match against, lower-cased once rather than per
        // keystroke. The full vendor name goes in it even though the column
        // shows the short one, so searching "Advanced Micro" still finds them.
        // The brackets matter. Written as two interpolated strings joined with
        // +, ToLowerInvariant applied to the second one only, so half the
        // haystack stayed capitalised and a lower-cased needle never met it:
        // "conexant" found nothing while Conexant sat on the screen.
        Haystack = ($"{Category} {Name} {row.Vendor} {Vendor} {Id} {Kext} "
                  + $"{Note} {Status} {Macos}").ToLowerInvariant();
    }

    /// <summary>A vendor name short enough to read in a column.
    ///
    /// The PCI ID Project writes them in full - "Advanced Micro Devices, Inc.
    /// [AMD/ATI]" - which wrapped to two lines on every one of sixty rows. The
    /// full name is still what a search matches on.</summary>
    public static string ShortName(string vendor) => Short(vendor);

    static string Short(string vendor)
    {
        if (vendor.Length == 0) return vendor;
        // the bracketed alias is the name everybody uses, where there is one
        var alias = System.Text.RegularExpressions.Regex.Match(vendor, @"\[([^\]]+)\]");
        if (alias.Success) return alias.Groups[1].Value.Split('/')[0];
        var cut = vendor.Split(new[] { ", Inc", " Inc", " Corp", " Technolog", " Co.," },
                               StringSplitOptions.None)[0];
        return cut.Trim().TrimEnd(',');
    }

    public string Category { get; }
    public string Name { get; }
    public string Vendor { get; }
    public string Id { get; }
    public string Kext { get; }
    public bool HasKext { get; }
    public string Note { get; }
    public bool HasNote { get; }
    public string Status { get; }
    public bool IsOk { get; }
    public bool IsBad { get; }
    public bool IsUnclear { get; }
    public string Macos { get; }
    public string Haystack { get; }
}

/// <summary>One community project as a card: its own words, and what it takes.</summary>
public sealed class CommunityItem
{
    public CommunityItem(CommunityProject p)
    {
        Name = p.Name;
        Matches = p.Matches;
        Stage = p.Stage;
        Install = p.Install == "system" ? "Installed on macOS"
                : p.Recipe ? "Offered in the EFI pane" : "Kext, its own way in";
        AiLabel = p.AiLevel switch { "written" => "AI-written", "assisted" => "AI-assisted", _ => "Not stated" };
        Haystack = $"{p.Name} {p.Role} {p.Covers} {p.Said} {p.Macos} {p.Repo} "
                 + string.Join(" ", p.Ids) + " " + string.Join(" ", p.Chips);
        Haystack = Haystack.ToLowerInvariant();
        Role = p.Role;
        Url = p.Url;
        Covers = p.Covers;
        Said = p.Said.Length > 0 ? $"\u201c{p.Said.Replace("**", "").Trim()}\u201d" : "";
        HasSaid = Said.Length > 0;
        // what can be shown about how it was written, labelled for what it is
        AiBadge = p.AiLevel switch { "written" => "AI-written", "assisted" => "AI-assisted", _ => "" };
        HasAi = AiBadge.Length > 0;
        AiWhy = HasAi ? $"{AiBadge}: {p.AiWhy}." : "";
        Uploaded = p.Uploaded.Length > 0
            ? $"Release file {p.Uploaded}." : "";
        HasUploaded = Uploaded.Length > 0;
        Report = p.Report;
        HasReport = Report.Length > 0;
        // what it matches, in the terms it matches by
        var matches = p.Devices > 0 ? $"{p.Devices} device id{(p.Devices == 1 ? "" : "s")}"
                    : p.Chips.Count > 0 ? $"chip families {string.Join(", ", p.Chips)}"
                    : p.Requires.Length > 0 ? $"needs {p.Requires}"
                    : "";
        Facts = string.Join("  ·  ", new[]
        {
            p.Release.Length > 0 ? p.Release : "no release",
            p.Licence, matches,
            p.Tested.Count > 0 ? $"run on {string.Join(", ", p.Tested)}" : "",
        }.Where(s => s.Length > 0));
        var said = p.Macos.Replace("**", "").Replace("| ", "").Trim('|', ' ');
        Macos = said.Length == 0 ? ""
              : said.StartsWith("macOS", StringComparison.Ordinal) ? said : $"macOS: {said}";
        var how = p.How.Length > 0 ? char.ToUpperInvariant(p.How[0]) + p.How[1..] : "";
        Where = p.Install == "system"
            ? $"Installed on macOS after it boots: {p.How}."
            : p.Recipe
            ? $"Offered at the end of the EFI pane when this machine matches, and never added "
              + "unasked; its own manual steps are applied as written. "
              + $"{how}."
            : $"Its own installer edits the EFI ({p.How}); nothing here adds it.";
        Needs = string.Join("  ", new[]
        {
            p.Needs.Length > 0 ? $"Needs {p.Needs}." : "",
            p.Conflicts.Count > 0 ? $"Not with {string.Join(" or ", p.Conflicts)}." : "",
        }.Where(s => s.Length > 0));
        HasNeeds = Needs.Length > 0;
    }

    public string Name { get; }
    public bool Matches { get; }
    public string Install { get; }
    public string AiLabel { get; }
    public string Haystack { get; }
    public string Role { get; }
    public string Stage { get; }
    public string Url { get; }
    public string Covers { get; }
    public string Said { get; }
    public bool HasSaid { get; }
    public bool HasAi { get; }
    public string AiBadge { get; }
    public string AiWhy { get; }
    public string Uploaded { get; }
    public bool HasUploaded { get; }
    public string Report { get; }
    public bool HasReport { get; }
    public string Facts { get; }
    public string Macos { get; }
    public string Where { get; }
    public string Needs { get; }
    public bool HasNeeds { get; }
}

public partial class DevicesView : UserControl
{
    const string Everything = "All";
    List<DeviceItem> _all = new();
    Task? _loaded;
    // which column orders the list, and which way. One at a time: two keys
    // would need a second arrow and nobody would read it.
    string _sortBy = "category";
    bool _ascending = true;

    public DevicesView()
    {
        InitializeComponent();
        Search.TextChanged += (_, _) => Draw();
        Category.SelectionChanged += (_, _) => Draw();
        Vendor.SelectionChanged += (_, _) => Draw();
        Status.SelectionChanged += (_, _) => Draw();
        SortCategory.Click += (_, _) => SortOn("category");
        SortName.Click += (_, _) => SortOn("name");
        ToShipped.IsCheckedChanged += (_, _) => ShowTab();
        ToCommunity.IsCheckedChanged += (_, _) => ShowTab();
        ToCommunity.Content = "Community";
        CommunitySearch.TextChanged += (_, _) => DrawCommunity();
        CommunityRole.SelectionChanged += (_, _) => DrawCommunity();
        CommunityInstall.SelectionChanged += (_, _) => DrawCommunity();
        CommunityAi.SelectionChanged += (_, _) => DrawCommunity();
        OnlyMine.IsCheckedChanged += (_, _) => DrawCommunity();
    }

    List<CommunityItem> _community = new();

    void DrawCommunity()
    {
        var needle = (CommunitySearch.Text ?? "").Trim().ToLowerInvariant();
        // each box says what it is about when nothing is picked in it, so the
        // first entry of each is its own word for "any", not a shared "All"
        string Pick(ComboBox box) => box.SelectedIndex > 0 ? box.SelectedItem as string ?? Everything
                                                           : Everything;
        var role = Pick(CommunityRole);
        var install = Pick(CommunityInstall);
        var ai = Pick(CommunityAi);
        var mine = OnlyMine.IsChecked == true;
        var kept = _community.Where(c =>
            (role == Everything || c.Role == role) &&
            (install == Everything || c.Install == install) &&
            (ai == Everything || c.AiLabel == ai) &&
            (!mine || c.Matches) &&
            (needle.Length == 0 || c.Haystack.Contains(needle, StringComparison.Ordinal))).ToList();
        Shown.ItemsSource = kept.Where(c => c.Stage != "watching").ToList();
        Watched.ItemsSource = kept.Where(c => c.Stage == "watching").ToList();
        CommunityCount.Text = kept.Count == _community.Count
            ? $"{_community.Count} projects"
            : $"{kept.Count} of {_community.Count} projects"
              + (mine && kept.Count == 0 ? " - nothing in the registry fits this machine" : "");
    }

    /// <summary>For the screenshot pass: open one tab or the other.</summary>
    public void ShowCommunity(bool on)
    {
        ToCommunity.IsChecked = on;
        ToShipped.IsChecked = !on;
        ShowTab();
    }

    void ShowTab()
    {
        var community = ToCommunity.IsChecked == true;
        Community.IsVisible = community;
        Filters.IsVisible = Table.IsVisible = !community;
    }

    /// <summary>Open a project's page in the browser.</summary>
    async void OpenProject(object? sender, Avalonia.Interactivity.RoutedEventArgs e)
    {
        if (sender is not Button { Tag: string url } || TopLevel.GetTopLevel(this) is not { } top)
            return;
        try { await top.Launcher.LaunchUriAsync(new Uri(url)); }
        catch (Exception) { /* no browser: the address is on the card's button */ }
    }

    /// <summary>Order by this column, or turn it round if it already is.</summary>
    void SortOn(string column)
    {
        if (_sortBy == column) _ascending = !_ascending;
        else { _sortBy = column; _ascending = true; }
        Draw();
    }

    // One read, and everybody waits for the same one. A bool guard let the
    // second caller past while the first was still awaiting: the nav's own
    // handler starts a Swap of its own, so two arrive together, and the second
    // returned to a pane that had not been filled yet. The screenshot pass
    // caught it on an empty list.
    public Task Load()
    {
        // and a read that threw is not a read: keeping the faulted task would
        // make every later look at this pane raise the same old exception
        if (_loaded is { IsFaulted: true }) _loaded = null;
        return _loaded ??= Fill();
    }

    async Task Fill()
    {
        var engine = Builder.Find(out var missing);
        if (engine is null) { Blurb.Text = missing; return; }

        Reading.Say("Reading every table this repository carries…");
        var (list, complaint) = await Inventory.Devices(engine);
        Reading.Say(null);
        if (list is null) { Blurb.Text = complaint; return; }

        // somebody else's drivers are their own tab now: a status column made
        // "this EFI drives it" and "a project somewhere does" read alike
        _all = list.Devices.Where(d => d.Status != "third-party")
                           .Select(d => new DeviceItem(d)).ToList();
        Blurb.Text = $"{_all.Count} devices across {list.Categories.Count} categories, "
                   + "read out of the same tables a build reads. A device being here "
                   + "means something in this repository claims it - not that every "
                   + "machine it sits in will work.";
        await FillCommunity(engine);
        Category.ItemsSource = new[] { "All categories" }.Concat(list.Categories).ToList();
        Vendor.ItemsSource = new[] { "All vendors" }
            .Concat(list.Vendors.Select(DeviceItem.ShortName).Distinct().OrderBy(v => v))
            .ToList();
        Status.ItemsSource = new[] { "Any support" }
            .Concat(list.Statuses.Where(s => s != "third-party")).ToList();
        Category.SelectedIndex = 0;
        Vendor.SelectedIndex = 0;
        Status.SelectedIndex = 0;
        Draw();
    }

    async Task FillCommunity(Located engine)
    {
        var (list, complaint) = await Inventory.Community(engine);
        if (list is null) { CommunityBlurb.Text = complaint; return; }
        _community = list.Projects.Select(p => new CommunityItem(p)).ToList();
        List<string> Choices(string any, IEnumerable<string> values) =>
            new[] { any }.Concat(values.Distinct().OrderBy(v => v)).ToList();
        CommunityRole.ItemsSource = Choices("All categories", _community.Select(c => c.Role));
        CommunityInstall.ItemsSource = Choices("Any way in", _community.Select(c => c.Install));
        CommunityAi.ItemsSource = new[] { "Any authorship", "AI-written", "AI-assisted", "Not stated" }.ToList();
        CommunityRole.SelectedIndex = CommunityInstall.SelectedIndex = CommunityAi.SelectedIndex = 0;
        DrawCommunity();
        CommunityBlurb.Text =
            "Drivers and add-ons nobody here wrote, for hardware this EFI has no answer "
            + "for or for things macOS never did on a PC. Each one is experimental by its "
            + "own account; every sentence on a card is the project's own, at the commit "
            + "recorded, and the device ids are read from its kext. A machine that has one "
            + "of these devices is told so on the Machine pane, beside Apple's answer and "
            + "never instead of it. AI-written means the project says its code was written "
            + "with an AI, or at least half its recent commits credit one as co-author; "
            + "AI-assisted means some do, or the repository carries an AI tool's "
            + "instructions. No label means nothing says either way. "
            + "If you run one, Report how it ran: what moves a driver from "
            + "experimental to recommended is people saying it worked.";
    }

    void Draw()
    {
        var needle = (Search.Text ?? "").Trim().ToLowerInvariant();
        // the first entry of each names its filter, and means everything
        string Picked(ComboBox box) => box.SelectedIndex > 0 ? box.SelectedItem as string ?? Everything
                                                             : Everything;
        var category = Picked(Category);
        var vendor = Picked(Vendor);
        var status = Picked(Status);

        var matching = _all.Where(d =>
            (category == Everything || d.Category == category) &&
            (vendor == Everything || d.Vendor == vendor) &&
            (status == Everything || d.Status == status) &&
            (needle.Length == 0 || d.Haystack.Contains(needle, StringComparison.Ordinal)));

        // ordinal-ignore-case, so "BCM4311" and "bcm4311" sort together and a
        // list of hex ids does not depend on anybody's locale
        var by = _sortBy == "name"
            ? (Func<DeviceItem, string>)(d => d.Name)
            : d => d.Category + " " + d.Name;
        matching = _ascending
            ? matching.OrderBy(by, StringComparer.OrdinalIgnoreCase)
            : matching.OrderByDescending(by, StringComparer.OrdinalIgnoreCase);
        var shown = matching.ToList();

        // the arrow goes on the column doing the ordering, and only that one
        var arrow = _ascending ? "  \u2191" : "  \u2193";
        SortCategoryLabel.Text = "CATEGORY" + (_sortBy == "category" ? arrow : "");
        SortNameLabel.Text = "DEVICE" + (_sortBy == "name" ? arrow : "");

        Rows.ItemsSource = shown;
        Count.Text = shown.Count == _all.Count
            ? $"{shown.Count} devices"
            : $"{shown.Count} of {_all.Count} devices";
    }
}
