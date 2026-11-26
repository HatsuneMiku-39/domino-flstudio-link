# With FL's record button armed, start Domino (through MMC, like pressing Play in Domino) and log what FL's
# Domino Link script sends back to Domino, plus the notes Domino plays. No test bridge needed.
#   python armed_start_test.py [locate ms]
import sys, os, time, ctypes, ctypes.wintypes as wt, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fl import Bridge, MIDIHDR
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
def key(vk):
    u.PostMessageW(main, 0x0100, vk, 0); time.sleep(0.03); u.PostMessageW(main, 0x0101, vk, 0xC0000001)

start = float(sys.argv[1]) if len(sys.argv) > 1 else 1700
already_armed = len(sys.argv) > 2 and sys.argv[2] == 'armed'   # R toggles: say so if FL is armed already
class TimedBridge(Bridge):
    def _callback(self, h, msg, inst, p1, p2):
        if msg == 0x3C4 and p1:
            hdr = MIDIHDR.from_address(p1)
            if hdr.dwBytesRecorded:
                self.done.append((time.perf_counter(), ctypes.string_at(hdr.lpData, hdr.dwBytesRecorded)))


br = TimedBridge()                 # receives what FL's script sends on loopMIDI "SysEx"
lis = listen_lib.Listener('1')
whole = int(round(start * 30 / 1000.0)); secs = whole // 30
try:
    t_r = time.perf_counter()
    if not already_armed:
        key(0x52)                  # R: arm FL's recording
    time.sleep(0.5)
    t0 = time.perf_counter()
    br.send([0xF0, 0x7F, 0x7F, 0x06, 0x44, 0x06, 0x01, (secs // 3600) | (3 << 5), (secs // 60) % 60, secs % 60, whole % 30, 0, 0xF7])
    br.send([0xF0, 0x7F, 0x7F, 0x06, 0x02, 0xF7])
    time.sleep(1.5)
    br.send([0xF0, 0x7F, 0x7F, 0x06, 0x01, 0xF7])
    time.sleep(0.6)
    msgs = ['%+7.0f ms  %s' % ((t - t0) * 1000, m.hex(' ')) for t, m in br.done if m[:4] == bytes([0xF0, 0x7F, 0x7F, 0x06])]
    key(0x52)                      # R again: disarm
finally:
    br.close(); lis.close()
print('R pressed at %+.0f ms; MMC on the SysEx port (ours at 0 and at ~1500 ms; anything else came from FL):' % ((t_r - t0) * 1000))
for m in msgs:
    print('  ', m)
notes = [((t - t0) * 1000, st & 15, d1, d2) for t, st, d1, d2 in lis.log if st & 0xF0 in (0x80, 0x90)]
print('Domino notes:', ['%.0f ms ch%d %s %d' % (t, c + 1, 'on' if v else 'off', k) for t, c, k, v in notes[:10]])
