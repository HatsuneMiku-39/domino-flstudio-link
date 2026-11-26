# Does Domino still react to MMC after it got menu commands (WM_COMMAND) like the helper's pre-roll sends?
#   python mmc_after_commands.py <Domino pid>
import sys, os, time, ctypes, ctypes.wintypes as wt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import listen_lib
from mmc import open_out, sysex
pid = int(sys.argv[1])
u = ctypes.WinDLL('user32')
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
mains = []
def cb(h, l):
    q = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(q))
    b = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, b, 256)
    if q.value == pid and u.IsWindowVisible(h) and b.value.endswith(' - Domino'): mains.append(h)
    return True
u.EnumWindows(WNDENUMPROC(cb), 0)
domino = mains[0]
out = open_out('SysEx')
def cmd(c):
    u.PostMessageW(domino, 0x0111, c, 0)
def mmc_cycle(label):
    lis = listen_lib.Listener('1')
    sysex(out, [0xF0, 0x7F, 0x7F, 0x06, 0x44, 0x06, 0x01, 0x60, 0, 0, 0, 0, 0xF7]); time.sleep(0.15)
    sysex(out, [0xF0, 0x7F, 0x7F, 0x06, 0x02, 0xF7]); time.sleep(0.3)
    sysex(out, [0xF0, 0x7F, 0x7F, 0x06, 0x01, 0xF7]); time.sleep(0.25)
    lis.close()
    ok = any(st & 0xF0 == 0x90 and d2 for t, st, d1, d2 in lis.log)
    print('%-58s MMC start %s' % (label, 'works' if ok else 'FAILS'))
    return ok
steps = [
    ('baseline', []),
    ('after Play/Stop, Play/Stop (start + stop by command)', [32886, 'wait', 32886]),
    ('after Play/Stop, then Stop (33131)', [32886, 'wait', 33131]),
    ('after Previous Quantize Unit + Play/Stop, Stop', [33326, 32886, 'wait', 33131]),
    ('after Next Quantize Unit', [33327]),
    ('after Previous Quantize Unit + Play/Stop, Play/Stop, Next', [33326, 32886, 'wait', 32886, 'wait', 33327]),
]
for label, seq in steps:
    for c in seq:
        if c == 'wait':
            time.sleep(0.6)
        else:
            cmd(c); time.sleep(0.05)
    time.sleep(0.4)
    if not mmc_cycle(label):
        break
