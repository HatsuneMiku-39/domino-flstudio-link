# Tests the helper's pre-roll against a running Domino without touching the keyboard: calls what Space would
# (Preroll.on_space / on_stopped) on Domino's window and logs where Domino starts, from its notes on loopMIDI "1".
# Use Domino with sync_test.mid (a C on channel 1 at bar 2 beat 1, 1714 ms at 140 BPM).
import sys, os, time, ctypes, ctypes.wintypes as wt, subprocess, importlib.machinery, importlib.util
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import listen_lib
from mmc import open_out, sysex

loader = importlib.machinery.SourceFileLoader('helper', os.path.join(here, 'python-helper', 'domino_link_helper.pyw'))
helper = importlib.util.module_from_spec(importlib.util.spec_from_loader('helper', loader)); loader.exec_module(helper)

u = ctypes.WinDLL('user32')
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
pid = int(subprocess.run(['powershell', '-NoProfile', '-Command', "(Get-Process Domino | Sort-Object StartTime | Select-Object -Last 1).Id"],
                         capture_output=True, text=True).stdout.split()[0])
def title(h):
    b = ctypes.create_unicode_buffer(512); u.GetWindowTextW(h, b, 512); return b.value
mains = []
def cb(h, l):
    q = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(q))
    if q.value == pid and u.IsWindowVisible(h) and title(h).endswith(' - Domino'): mains.append(h)
    return True
u.EnumWindows(WNDENUMPROC(cb), 0)
domino = mains[0]

pre = helper.Preroll('quantize')
pre.active_domino = lambda: domino          # as if Domino were the active window
pre.typing = staticmethod(lambda h: False)

# Domino's time code, as the helper reads it on loopMIDI "SysEx"
timecode = []
def on_sync(h, msg, inst, p1, p2):
    if msg == 0x3C3 and ((p1 or 0) & 0xFF) == 0xF1:
        timecode.append((time.perf_counter(), ((p1 or 0) >> 8) & 0x7F))
sync_cb = helper.CB(on_sync)
hs = ctypes.c_void_p()
idx = helper.device_index(helper.mm.midiInGetNumDevs, helper.mm.midiInGetDevCapsW, helper.INCAPS, 'SysEx')
helper.mm.midiInOpen(ctypes.byref(hs), idx, ctypes.cast(sync_cb, ctypes.c_void_p), None, 0x30000); helper.mm.midiInStart(hs)
out = open_out('SysEx')


def locate(ms):
    whole = int(round(ms * 30 / 1000.0)); secs = whole // 30
    sysex(out, [0xF0, 0x7F, 0x7F, 0x06, 0x44, 0x06, 0x01, (secs // 3600) | (3 << 5), (secs // 60) % 60, secs % 60, whole % 30, 0, 0xF7])


def first_note(action, secs=0.6):
    lis = listen_lib.Listener('1')
    t0 = time.perf_counter()
    action()
    end = t0 + secs
    while time.perf_counter() < end:
        while timecode:
            pre.on_timecode(*timecode.pop(0))
        time.sleep(0.002)
    lis.close()
    notes = [((t - t0) * 1000, d1) for t, st, d1, d2 in lis.log if st & 0xF0 == 0x90 and d2]
    return notes[0] if notes else None


def plain_play():
    u.PostMessageW(domino, 0x0111, helper.Preroll.PLAY_STOP, 0)


def stop_and_settle(with_preroll):
    if with_preroll:
        pre.on_space(playing=True)          # Space while playing: stop
    else:
        u.PostMessageW(domino, 0x0111, helper.Preroll.PLAY_STOP, 0)
    time.sleep(0.35)
    if with_preroll:
        pre.on_stopped()                    # what the helper does when Domino's clock stops
    time.sleep(0.3)


for spot, label in ((1700, 'just before the bar-2 C'), (0, 'song start')):
    locate(spot); time.sleep(0.4)
    a = first_note(plain_play); stop_and_settle(False)
    locate(spot); time.sleep(0.4)
    b = first_note(lambda: pre.on_space(playing=False)); start_pos = pre.start_pos; stop_and_settle(True)
    c = first_note(plain_play); stop_and_settle(False)
    print('%-24s plain Play: first note at %5.0f ms | Space with pre-roll: %5.0f ms (started at %s ms) | plain Play afterwards: %5.0f ms'
          % (label, a[0], b[0], 'n/a' if start_pos is None else '%.0f' % start_pos, c[0]))
helper.mm.midiInStop(hs); helper.mm.midiInClose(hs)
