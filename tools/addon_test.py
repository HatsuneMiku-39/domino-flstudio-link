# Tests the Domino add-on (version.dll) in a running Domino with sync_test.mid (a C at bar 2 beat 1 = 1714 ms):
# Domino's Play/Stop command with the pre-roll, the playhead coming back after the stop, and the tempo message
# the add-on sends on loopMIDI "SysEx".
#   python addon_test.py <Domino pid>
import sys, os, time, ctypes, ctypes.wintypes as wt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fl import Bridge, MIDIHDR
import listen_lib

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


class TimedBridge(Bridge):
    def _callback(self, h, msg, inst, p1, p2):
        if msg == 0x3C4 and p1:
            hdr = MIDIHDR.from_address(p1)
            if hdr.dwBytesRecorded:
                self.done.append((time.perf_counter(), ctypes.string_at(hdr.lpData, hdr.dwBytesRecorded)))


br = TimedBridge()


def locate(ms):
    whole = int(round(ms * 30 / 1000.0)); secs = whole // 30
    br.send([0xF0, 0x7F, 0x7F, 0x06, 0x44, 0x06, 0x01, (secs // 3600) | (3 << 5), (secs // 60) % 60, secs % 60, whole % 30, 0, 0xF7])


def first_note(start, secs=1.0, stop=None):
    lis = listen_lib.Listener('1')
    t0 = time.perf_counter()
    start()
    time.sleep(secs)
    (stop or (lambda: None))()
    time.sleep(0.4)
    lis.close()
    clocks = [t for t, st, a, b in lis.log if st == 0xF8]
    notes = [t for t, st, a, b in lis.log if st & 0xF0 == 0x90 and b]
    if not clocks or not notes:
        return None
    return (notes[0] - clocks[0]) * 1000


play_stop = lambda: u.PostMessageW(domino, 0x0111, 32886, 0)      # Domino's own Play/Stop command (Space)
mmc_play = lambda: br.send([0xF0, 0x7F, 0x7F, 0x06, 0x02, 0xF7])   # start from outside (like FL does)
mmc_stop = lambda: br.send([0xF0, 0x7F, 0x7F, 0x06, 0x01, 0xF7])
try:
    locate(1700); time.sleep(0.4)
    a = first_note(mmc_play, stop=mmc_stop)
    print('start from outside (MMC), no pre-roll:  first note %.0f ms after the start' % a)
    locate(1700); time.sleep(0.4)
    br.done.clear()
    b = first_note(play_stop, stop=play_stop)
    print("Domino's Play/Stop with the add-on:     first note %.0f ms after the start" % b)
    time.sleep(0.5)
    c = first_note(mmc_play, stop=mmc_stop)
    print('after stopping, start from outside:     first note %.0f ms after the start (playhead back?)' % c)
    tempos = [m for t, m in br.done if m[:3] == bytes([0xF0, 0x7D, 0x10])]
    print('tempo messages from the add-on:', ['%.2f BPM' % (((m[3] << 14) | (m[4] << 7) | m[5]) / 100.0) for m in tempos])
finally:
    br.close()
