# Send MMC commands to Domino through the loopMIDI "SysEx" port (what pressing Play/Stop in another program does).
#   python mmc.py play [locate_ms]   |   python mmc.py stop
import ctypes, ctypes.wintypes as wt, sys, time

mm = ctypes.WinDLL('winmm')


class MIDIHDR(ctypes.Structure):
    _fields_ = [('lpData', ctypes.c_char_p), ('dwBufferLength', wt.DWORD), ('dwBytesRecorded', wt.DWORD),
                ('dwUser', ctypes.c_void_p), ('dwFlags', wt.DWORD), ('lpNext', ctypes.c_void_p),
                ('reserved', ctypes.c_void_p), ('dwOffset', wt.DWORD), ('dwReserved', ctypes.c_void_p * 8)]


class CAPS(ctypes.Structure):
    _fields_ = [('wMid', wt.WORD), ('wPid', wt.WORD), ('vDriverVersion', wt.DWORD), ('szPname', wt.WCHAR * 32),
                ('wTechnology', wt.WORD), ('wVoices', wt.WORD), ('wNotes', wt.WORD), ('wChannelMask', wt.WORD), ('dwSupport', wt.DWORD)]


mm.midiOutOpen.argtypes = [ctypes.POINTER(ctypes.c_void_p), wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
mm.midiOutPrepareHeader.argtypes = [ctypes.c_void_p, ctypes.POINTER(MIDIHDR), wt.UINT]
mm.midiOutLongMsg.argtypes = [ctypes.c_void_p, ctypes.POINTER(MIDIHDR), wt.UINT]
mm.midiOutUnprepareHeader.argtypes = [ctypes.c_void_p, ctypes.POINTER(MIDIHDR), wt.UINT]
mm.midiOutClose.argtypes = [ctypes.c_void_p]


def open_out(name):
    for i in range(mm.midiOutGetNumDevs()):
        c = CAPS(); mm.midiOutGetDevCapsW(i, ctypes.byref(c), ctypes.sizeof(c))
        if c.szPname == name:
            h = ctypes.c_void_p()
            if mm.midiOutOpen(ctypes.byref(h), i, None, None, 0) == 0:
                return h
    raise KeyError(name)


def sysex(h, data):
    buf = ctypes.create_string_buffer(bytes(data), len(data))
    hdr = MIDIHDR(); hdr.lpData = ctypes.cast(buf, ctypes.c_char_p); hdr.dwBufferLength = len(data)
    mm.midiOutPrepareHeader(h, ctypes.byref(hdr), ctypes.sizeof(hdr))
    mm.midiOutLongMsg(h, ctypes.byref(hdr), ctypes.sizeof(hdr))
    for _ in range(100):
        if hdr.dwFlags & 1:   # MHDR_DONE
            break
        time.sleep(0.005)
    mm.midiOutUnprepareHeader(h, ctypes.byref(hdr), ctypes.sizeof(hdr))


if __name__ == '__main__':
    h = open_out('SysEx')
    if sys.argv[1] == 'play':
        ms = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
        frames = ms * 30 / 1000.0; whole = int(frames); sub = int((frames - whole) * 100)
        secs = whole // 30
        sysex(h, [0xF0, 0x7F, 0x7F, 0x06, 0x44, 0x06, 0x01, (secs // 3600) | (3 << 5), (secs // 60) % 60, secs % 60, whole % 30, sub, 0xF7])
        sysex(h, [0xF0, 0x7F, 0x7F, 0x06, 0x02, 0xF7])
        print('sent locate %.0f ms + play at %.3f' % (ms, time.perf_counter()))
    else:
        sysex(h, [0xF0, 0x7F, 0x7F, 0x06, 0x01, 0xF7])
        print('sent stop')
    mm.midiOutClose(h)
