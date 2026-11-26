# Minimal WinMM MIDI input logger (short messages only).
import ctypes, ctypes.wintypes as wt, time

mm = ctypes.WinDLL('winmm')
CB = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)


class CAPS(ctypes.Structure):
    _fields_ = [('wMid', wt.WORD), ('wPid', wt.WORD), ('vDriverVersion', wt.DWORD), ('szPname', wt.WCHAR * 32), ('dwSupport', wt.DWORD)]


mm.midiInOpen.argtypes = [ctypes.POINTER(ctypes.c_void_p), wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
for fn in ('midiInStart', 'midiInStop', 'midiInClose'):
    getattr(mm, fn).argtypes = [ctypes.c_void_p]


class Listener:
    def __init__(self, name):
        self.log = []
        self._cb = CB(self._callback)
        self.h = ctypes.c_void_p()
        for i in range(mm.midiInGetNumDevs()):
            c = CAPS(); mm.midiInGetDevCapsW(i, ctypes.byref(c), ctypes.sizeof(c))
            if c.szPname == name:
                assert mm.midiInOpen(ctypes.byref(self.h), i, ctypes.cast(self._cb, ctypes.c_void_p), None, 0x30000) == 0
                break
        else:
            raise KeyError(name)
        mm.midiInStart(self.h)

    def _callback(self, h, msg, inst, p1, p2):
        if msg == 0x3C3:                    # MIM_DATA
            d = p1 or 0
            self.log.append((time.perf_counter(), d & 0xFF, (d >> 8) & 0xFF, (d >> 16) & 0xFF))

    def close(self):
        mm.midiInStop(self.h); mm.midiInClose(self.h)
