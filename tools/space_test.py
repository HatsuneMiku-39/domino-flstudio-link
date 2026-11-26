# Press Space in FL (posted to its main window), log the MMC the Domino Link script sends and what Domino plays.
import sys, os, time, ctypes, ctypes.wintypes as wt, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fl import Bridge
import listen_lib
u = ctypes.WinDLL('user32')
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
pid = int(subprocess.run(['powershell', '-NoProfile', '-Command', '(Get-Process FL64).Id'], capture_output=True, text=True).stdout.split()[0])
found = []
def cb(h, l):
    q = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(q))
    c = ctypes.create_unicode_buffer(64); u.GetClassNameW(h, c, 64)
    if q.value == pid and c.value == 'TFruityLoopsMainForm': found.append(h)
    return True
u.EnumWindows(WNDENUMPROC(cb), 0)
main = found[0]
def space():
    u.PostMessageW(main, 0x0100, 0x20, 0x00390001); time.sleep(0.03); u.PostMessageW(main, 0x0101, 0x20, 0xC0390001)
br = Bridge()   # only used to receive SysEx on the loopMIDI "SysEx" port
lis = listen_lib.Listener('1')
try:
    t0 = time.perf_counter(); space(); time.sleep(1.6)
    t1 = time.perf_counter(); space(); time.sleep(0.6)
finally:
    msgs = list(br.done); br.close(); lis.close()
mmc = [m.hex(' ') for m in msgs if m[:4] == bytes([0xF0, 0x7F, 0x7F, 0x06])]
print('MMC from the script:', mmc)
notes = [((t - t0) * 1000, st & 15, d1) for t, st, d1, d2 in lis.log if st & 0xF0 == 0x90 and d2]
print('Domino notes:', ['%.0f ms ch%d key%d' % (t, c + 1, k) for t, c, k in notes[:6]], '...', len(notes), 'in total')
