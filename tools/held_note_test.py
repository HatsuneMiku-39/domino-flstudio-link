# Does FL silence a note that is already playing when FL starts (following Domino) or when its playhead jumps?
# Holds one long note on loopMIDI "1" channel 1 (an FL instrument there), starts Domino through MMC under it, makes
# Domino jump, and prints FL's level on Voicemeeter's "Voicemeeter Input" strip over time.
# Use a Domino song with nothing on port A channel 1, so only the held note sounds.
#   python held_note_test.py [start|jump|none]
import sys, os, time, ctypes, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mid
from mmc import open_out, sysex

mode = sys.argv[1] if len(sys.argv) > 1 else 'jump'
vm = ctypes.WinDLL(r'C:\Program Files (x86)\VB\Voicemeeter\VoicemeeterRemote64.dll')
vm.VBVMR_Login(); time.sleep(0.3)
h = open_out('SysEx')


def level():
    v = ctypes.c_float(); m = 0.0
    for ch in (10, 11):
        vm.VBVMR_GetLevel(0, ch, ctypes.byref(v)); m = max(m, v.value)
    return 20 * math.log10(m) if m > 0 else -200.0


def locate(ms):
    whole = int(round(ms * 30 / 1000.0)); secs = whole // 30
    sysex(h, [0xF0, 0x7F, 0x7F, 0x06, 0x44, 0x06, 0x01, (secs // 3600) | (3 << 5), (secs // 60) % 60, secs % 60, whole % 30, 0, 0xF7])


quiet = time.perf_counter()
while level() > -85 and time.perf_counter() - quiet < 12:
    time.sleep(0.01)
time.sleep(0.5)
log, events = [], []
t0 = time.perf_counter()
mid.send(1, 0x90, 60, 110)
done = set()
while time.perf_counter() - t0 < 3.0:
    t = time.perf_counter() - t0
    if mode in ('start', 'jump') and t > 0.3 and 'play' not in done:
        locate(0); sysex(h, [0xF0, 0x7F, 0x7F, 0x06, 0x02, 0xF7]); done.add('play'); events.append((t, 'Domino play'))
    if mode == 'jump' and t > 1.2 and 'jump' not in done:
        locate(6000); done.add('jump'); events.append((t, 'Domino jump'))
    if t > 2.5 and 'off' not in done:
        mid.send(1, 0x80, 60, 0); done.add('off'); events.append((t, 'note off'))
    log.append((t, level()))
    time.sleep(0.004)
if 'play' in done:
    sysex(h, [0xF0, 0x7F, 0x7F, 0x06, 0x01, 0xF7])
mid.send(1, 0x80, 60, 0)
vm.VBVMR_Logout()
print(mode, 'events:', ', '.join('%s at %.2f s' % (e, t) for t, e in events))
for a in [x / 10.0 for x in range(0, 30, 2)]:
    seg = [l for t, l in log if a <= t < a + 0.2]
    print('  %.1f-%.1f s: max %6.1f dB  min %6.1f dB' % (a, a + 0.2, max(seg), min(seg)))
