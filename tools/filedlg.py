# Fill FL Studio's open/save file dialog (standard Windows dialog) with a path and press its OK button.
#   python filedlg.py <full path>
import ctypes, ctypes.wintypes as wt, subprocess, time, sys
u = ctypes.WinDLL('user32')
u.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, ctypes.c_void_p]; u.SendMessageW.restype = ctypes.c_ssize_t
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
pid = int(subprocess.run(['powershell', '-NoProfile', '-Command', '(Get-Process FL64).Id'], capture_output=True, text=True).stdout.strip())
def cls(h):
    c = ctypes.create_unicode_buffer(128); u.GetClassNameW(h, c, 128); return c.value
def title(h):
    n = u.GetWindowTextLengthW(h); b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1); return b.value
dlg = []
def cb(h, l):
    q = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(q))
    if q.value == pid and u.IsWindowVisible(h) and cls(h) == '#32770': dlg.append(h)
    return True
u.EnumWindows(WNDENUMPROC(cb), 0)
d = dlg[0]
kids = []
def cb2(c, l):
    kids.append(c); return True
u.EnumChildWindows(d, WNDENUMPROC(cb2), 0)
e = ([c for c in kids if cls(c) == 'Edit' and u.GetDlgCtrlID(c) in (1001, 1148)] or [c for c in kids if cls(c) == 'Edit'])[0]
buf = ctypes.create_unicode_buffer(sys.argv[1])
u.SendMessageW(e, 0x000C, 0, ctypes.cast(buf, ctypes.c_void_p))
time.sleep(0.3)
ok = u.GetDlgItem(d, 1)
print('dialog %r, pressing %r' % (title(d), title(ok)))
u.PostMessageW(ok, 0x00F5, 0, 0)
time.sleep(2)
