# How many MMC messages does Domino take before it stops reacting? Restarts the test Domino with sync_test.mid,
# then repeats locate 0 / play / stop and checks that the song's first note comes each time.
#   python mmc_stress.py <Domino.exe> <song> [cycles] [extra sysex per cycle]
import sys, os, time, subprocess, ctypes, ctypes.wintypes as wt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import listen_lib
from mmc import open_out, sysex

exe, song = sys.argv[1], sys.argv[2]
cycles = int(sys.argv[3]) if len(sys.argv) > 3 else 20
extra = int(sys.argv[4]) if len(sys.argv) > 4 else 0
u = ctypes.WinDLL('user32')
u.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
def wins(pid):
    out = []
    def cb(h, l):
        q = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(q))
        if q.value == pid and u.IsWindowVisible(h): out.append(h)
        return True
    u.EnumWindows(WNDENUMPROC(cb), 0)
    return out
def text(h, f):
    b = ctypes.create_unicode_buffer(256); f(h, b, 256); return b.value

subprocess.run(['taskkill', '/IM', 'Domino.exe', '/F', '/FI', 'WINDOWTITLE ne x'], capture_output=True) if False else None
p = subprocess.Popen([exe, song], cwd=os.path.dirname(exe), creationflags=0x00000008)
time.sleep(5)
for h in wins(p.pid):                         # "restore Control Change Macros?" -> No
    if text(h, u.GetClassNameW) == '#32770':
        btns = []
        def cb(c, l):
            if text(c, u.GetClassNameW) == 'Button': btns.append(c)
            return True
        u.EnumChildWindows(h, WNDENUMPROC(cb), 0)
        if len(btns) >= 2: u.SendMessageW(btns[1], 0x00F5, 0, 0)
time.sleep(1)
out = open_out('SysEx')
sent = 0
def mmc(*data):
    global sent
    sysex(out, [0xF0, 0x7F, 0x7F, 0x06] + list(data) + [0xF7]); sent += 1
for k in range(cycles):
    for _ in range(extra):                   # other SysEx on the same port (like the helper's tempo messages)
        sysex(out, [0xF0, 0x7D, 0x10, 0x00, 0x6D, 0x30, 0xF7]); sent += 1
    lis = listen_lib.Listener('1')
    mmc(0x44, 0x06, 0x01, 0x60, 0, 0, 0, 0); time.sleep(0.15)
    t0 = time.perf_counter(); mmc(0x02); time.sleep(0.3)
    mmc(0x01); time.sleep(0.2)
    lis.close()
    notes = [(t - t0) * 1000 for t, st, d1, d2 in lis.log if st & 0xF0 == 0x90 and d2]
    ok = bool(notes) and notes[0] < 50
    print('cycle %2d (sysex messages so far %3d): %s' % (k + 1, sent, 'started, first note %.0f ms' % notes[0] if notes else 'NO START'))
    if not ok:
        break
print('test Domino pid', p.pid)
