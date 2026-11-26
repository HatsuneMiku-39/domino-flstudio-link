# Compares FL's audio paths: time from a MIDI note into loopMIDI "1" (an FL instrument on port 1, channel 1) until
# FL's sound reaches -70 dB on the Voicemeeter strip FL plays into. The instrument's attack adds the same amount on
# both paths, so only the difference between paths means something. What comes after Voicemeeter (A1 output, the
# headset) is the same for both and comes on top.
#   python latency_test.py vaio|cable [notes]
#     vaio:  FL on "Voicemeeter Virtual ASIO" (strip "Voicemeeter Input")
#     cable: FL on "FL Studio ASIO" -> Windows default device "CABLE Input" (strip "CABLE Output")
import sys, os, time, ctypes, math, statistics
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mid

CHANNELS = {'vaio': (10, 11), 'cable': (0, 1)}   # Voicemeeter Potato input meter channels of those strips
THRESHOLD_DB, QUIET_DB = -70.0, -85.0
path = sys.argv[1]
count = int(sys.argv[2]) if len(sys.argv) > 2 else 6

vm = ctypes.WinDLL(r'C:\Program Files (x86)\VB\Voicemeeter\VoicemeeterRemote64.dll')
vm.VBVMR_Login()
time.sleep(0.3)


def level_db():
    v = ctypes.c_float(); best = 0.0
    for ch in CHANNELS[path]:
        vm.VBVMR_GetLevel(0, ch, ctypes.byref(v)); best = max(best, v.value)
    return 20 * math.log10(best) if best > 0 else -200.0


results = []
try:
    for k in range(count):
        quiet_since = None
        t_wait = time.perf_counter()
        while time.perf_counter() - t_wait < 10:       # wait for 0.3 s below QUIET_DB (the last note's tail)
            if level_db() < QUIET_DB:
                quiet_since = quiet_since or time.perf_counter()
                if time.perf_counter() - quiet_since > 0.3:
                    break
            else:
                quiet_since = None
            time.sleep(0.005)
        t0 = time.perf_counter()
        mid.send(1, 0x90, 60, 110)
        while time.perf_counter() - t0 < 1.0:
            if level_db() > THRESHOLD_DB:
                results.append((time.perf_counter() - t0) * 1000)
                break
            time.sleep(0.0005)
        time.sleep(0.6)
        mid.send(1, 0x80, 60, 0)
finally:
    vm.VBVMR_Logout()
if results:
    print('%s: %d of %d notes, median %.1f ms, min %.1f, max %.1f' % (path, len(results), count, statistics.median(results), min(results), max(results)))
else:
    print('%s: no sound seen' % path)
