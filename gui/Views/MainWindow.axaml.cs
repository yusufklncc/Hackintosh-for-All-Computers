using Avalonia.Controls;

namespace Shell.Views;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        // what the program carries, said once and not repeated on every pane
        Standing.Text = "179 configs\n41 kexts vendored\nno network needed";
    }
}
