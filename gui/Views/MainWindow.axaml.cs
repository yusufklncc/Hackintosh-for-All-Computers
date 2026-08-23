using Avalonia.Controls;
using Avalonia.Markup.Xaml;

namespace Shell.Views;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        AvaloniaXamlLoader.Load(this);
        // what the program carries, said once and not repeated on every pane
        this.FindControl<TextBlock>("Standing")!.Text =
            "179 configs\n41 kexts vendored\nno network needed";
    }
}
