"""The same empty window, in what the builder is already written in.

Not a proposal - a second number. The Avalonia figure means nothing on its own;
what matters is the difference between it and the alternatives, measured the
same way on the same machine."""
import ctypes
import os
import sys
import tkinter as tk
from tkinter import ttk


def peak_bytes():
    """Peak working set of this process, however this platform reports it."""
    if sys.platform == 'win32':
        class Counters(ctypes.Structure):
            _fields_ = [('cb', ctypes.c_uint32), ('PageFaultCount', ctypes.c_uint32),
                        ('PeakWorkingSetSize', ctypes.c_size_t),
                        ('WorkingSetSize', ctypes.c_size_t),
                        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                        ('PagefileUsage', ctypes.c_size_t),
                        ('PeakPagefileUsage', ctypes.c_size_t)]
        c = Counters()
        c.cb = ctypes.sizeof(c)
        ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return c.PeakWorkingSetSize, c.WorkingSetSize
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports kilobytes here, macOS bytes
    return (peak * 1024 if sys.platform.startswith('linux') else peak), 0


def main():
    root = tk.Tk()
    root.title('Hackintosh EFI Builder')
    root.geometry('900x600')
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Hackintosh EFI Builder',
              font=('TkDefaultFont', 18)).pack(anchor='w', pady=(0, 12))
    ttk.Label(frame, text='A window, a theme, and nothing else.').pack(anchor='w')
    ttk.Progressbar(frame, value=40, maximum=100).pack(fill='x', pady=12)
    ttk.Button(frame, text='Build').pack(anchor='w')

    def report():
        peak, now = peak_bytes()
        lines = [f'peak_working_set_bytes={peak}', f'working_set_bytes={now}']
        for line in lines:
            print(line)
        into = os.environ.get('BENCH_OUT')
        if into:
            with open(into, 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(lines) + '\n')
        root.destroy()

    root.after(5000, report)     # the same five seconds the other one waits
    root.mainloop()


if __name__ == '__main__':
    main()
