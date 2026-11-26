# Send test MIDI into loopMIDI ports (WinMM) for the Domino -> FL tests.
#   python mid.py route              notes on several port/channel pairs, each pair with its own key
#   python mid.py cc <port> <ch>     note + sustain pedal, pitch bend, mod wheel, volume on one port/channel
#   python mid.py raw <port> <hex bytes...>
import ctypes, ctypes.wintypes as wt, time, sys

mm = ctypes.WinDLL('winmm')
mm.midiOutOpen.argtypes = [ctypes.POINTER(ctypes.c_void_p), wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
mm.midiOutShortMsg.argtypes = [ctypes.c_void_p, wt.DWORD]
mm.midiOutClose.argtypes = [ctypes.c_void_p]


class CAPS(ctypes.Structure):
    _fields_ = [('wMid', wt.WORD), ('wPid', wt.WORD), ('vDriverVersion', wt.DWORD), ('szPname', wt.WCHAR * 32),
                ('wTechnology', wt.WORD), ('wVoices', wt.WORD), ('wNotes', wt.WORD), ('wChannelMask', wt.WORD), ('dwSupport', wt.DWORD)]


_open = {}
def out(name):
    if name not in _open:
        for i in range(mm.midiOutGetNumDevs()):
            c = CAPS(); mm.midiOutGetDevCapsW(i, ctypes.byref(c), ctypes.sizeof(c))
            if c.szPname == name:
                h = ctypes.c_void_p()
                r = mm.midiOutOpen(ctypes.byref(h), i, None, None, 0)
                if r: raise OSError('midiOutOpen(%s) failed: %d' % (name, r))
                _open[name] = h
                break
        else:
            raise KeyError('no MIDI output named %r' % name)
    return _open[name]


def send(port, status, d1=0, d2=0):
    mm.midiOutShortMsg(out(str(port)), status | (d1 << 8) | (d2 << 16))


def play(schedule):
    """schedule: list of (ms, port, status, d1, d2); sent at those times from now."""
    for port in {x[1] for x in schedule}:
        out(str(port))          # open every port first, so the first message isn't late
    t0 = time.perf_counter()
    for ms, port, st, d1, d2 in sorted(schedule, key=lambda x: x[0]):
        while (time.perf_counter() - t0) * 1000 < ms:
            pass
        send(port, st, d1, d2)
        print('%7.1f ms  port %s  %02X %d %d' % ((time.perf_counter() - t0) * 1000, port, st, d1, d2))


def note(sched, ms, port, ch, key, vel=100, dur=250):
    sched.append((ms, port, 0x90 | (ch - 1), key, vel))
    sched.append((ms + dur, port, 0x80 | (ch - 1), key, 0))


if __name__ == '__main__':
    cmd = sys.argv[1]
    s = []
    if cmd == 'route':
        # (port, MIDI channel, key): each pair gets its own key so the recording shows where it went
        pairs = [(2, 1, 60), (2, 2, 64), (3, 1, 67), (3, 5, 71), (4, 1, 74)]
        t = 0
        for rep in range(2):
            for port, ch, key in pairs:
                note(s, t, port, ch, key); t += 400
    elif cmd == 'quirk':
        # port 2 ch 2 (claimed by MIDI Out #2) while the port-2/ch-1 channel is selected,
        # then port 2 ch 1 at several velocities, then an unclaimed port
        t = 0
        for rep in range(2):
            note(s, t, 2, 2, 64); t += 400
        for v in (1, 20, 40, 64, 80, 100, 110, 127):
            note(s, t, 2, 1, 60, vel=v); t += 400
        note(s, t, 4, 1, 74)
    elif cmd == 'pedal':
        # sustain pedal on port 2 ch 1 only; short notes on ch 1, ch 2 (same port) and port 3 ch 1
        s += [(0, 2, 0xB0, 64, 127)]
        note(s, 200, 2, 1, 60, dur=150)
        note(s, 600, 2, 2, 64, dur=150)
        note(s, 1000, 3, 1, 67, dur=150)
        s += [(2500, 2, 0xB0, 64, 0)]
    elif cmd == 'cc':
        port, ch = int(sys.argv[2]), int(sys.argv[3]); c = ch - 1
        s += [(0, port, 0xB0 | c, 7, 40),          # volume
              (100, port, 0xB0 | c, 1, 127),       # mod wheel up
              (200, port, 0xE0 | c, 0, 96),        # pitch bend up (value 12288)
              (300, port, 0xB0 | c, 64, 127),      # sustain pedal down
              (400, port, 0x90 | c, 62, 100),      # note on D
              (700, port, 0x80 | c, 62, 0)]        # note off while pedal is down
        if '--release' in sys.argv:
            s += [(3000, port, 0xB0 | c, 64, 0), (3000, port, 0xE0 | c, 0, 64), (3000, port, 0xB0 | c, 1, 0), (3000, port, 0xB0 | c, 7, 100)]
    elif cmd == 'raw':
        port = int(sys.argv[2]); bs = [int(x, 16) for x in sys.argv[3:]]
        s = [(0, port, bs[0], bs[1] if len(bs) > 1 else 0, bs[2] if len(bs) > 2 else 0)]
    play(s)
    time.sleep(0.2)
    for h in _open.values():
        mm.midiOutClose(h)
