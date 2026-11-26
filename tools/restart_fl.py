# Close FL (no save prompt expected: save first) and start it again with a project.
#   python restart_fl.py <project.flp>
import ctypes, ctypes.wintypes as wt, subprocess, time, sys
u = ctypes.WinDLL('user32')
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
def cls(h):
    c = ctypes.create_unicode_buffer(128); u.GetClassNameW(h, c, 128); return c.value
def title(h):
    n = u.GetWindowTextLengthW(h); b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1); return b.value
def pids():
    out = subprocess.run(['powershell', '-NoProfile', '-Command', '(Get-Process FL64 -ErrorAction SilentlyContinue).Id'], capture_output=True, text=True).stdout.split()
    return [int(x) for x in out]
def wins(pid):
    hs = []
    def cb(h, l):
        q = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(q))
        if q.value == pid: hs.append(h)
        return True
    u.EnumWindows(WNDENUMPROC(cb), 0)
    return hs
for pid in pids():
    for h in wins(pid):
        if cls(h) == 'TFruityLoopsMainForm':
            u.PostMessageW(h, 0x0010, 0, 0)
for _ in range(40):
    time.sleep(0.5)
    if not pids():
        break
else:
    for pid in pids():
        for h in wins(pid):
            if u.IsWindowVisible(h): print('still open:', cls(h), repr(title(h)))
    sys.exit('FL did not close')
p = subprocess.Popen([r'C:\_main\Image-Line\FL64.exe', sys.argv[1]], cwd=r'C:\_main\Image-Line', creationflags=0x00000008)
main = app = None
for _ in range(90):
    time.sleep(1)
    d = {cls(h): h for h in wins(p.pid)}
    if 'TFruityLoopsMainForm' in d and '.flp' in title(d['TFruityLoopsMainForm']):
        main, app = d['TFruityLoopsMainForm'], d.get('TApplication'); break
time.sleep(5)
if app: u.ShowWindow(app, 9)
time.sleep(0.5); u.ShowWindow(main, 3); time.sleep(0.5); u.SetForegroundWindow(main)
print('FL restarted', p.pid, title(main))
