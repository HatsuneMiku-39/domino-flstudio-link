# Run Python inside FL Studio through the test bridge in the Domino Link script (SysEx over loopMIDI "SysEx").
#   python fl.py "<code>"      (use out(...) to print; FL modules are available by name)
# As a module: Bridge().run(code) keeps the ports open for several commands.
import ctypes, ctypes.wintypes as wt, sys, time, random, threading

mm = ctypes.WinDLL('winmm')


class MIDIHDR(ctypes.Structure):
    _fields_ = [('lpData', ctypes.c_void_p), ('dwBufferLength', wt.DWORD), ('dwBytesRecorded', wt.DWORD),
                ('dwUser', ctypes.c_void_p), ('dwFlags', wt.DWORD), ('lpNext', ctypes.c_void_p),
                ('reserved', ctypes.c_void_p), ('dwOffset', wt.DWORD), ('dwReserved', ctypes.c_void_p * 8)]


class INCAPS(ctypes.Structure):
    _fields_ = [('wMid', wt.WORD), ('wPid', wt.WORD), ('vDriverVersion', wt.DWORD), ('szPname', wt.WCHAR * 32), ('dwSupport', wt.DWORD)]


class OUTCAPS(ctypes.Structure):
    _fields_ = [('wMid', wt.WORD), ('wPid', wt.WORD), ('vDriverVersion', wt.DWORD), ('szPname', wt.WCHAR * 32),
                ('wTechnology', wt.WORD), ('wVoices', wt.WORD), ('wNotes', wt.WORD), ('wChannelMask', wt.WORD), ('dwSupport', wt.DWORD)]


CB = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
for fn in ('midiInOpen', 'midiOutOpen'):
    getattr(mm, fn).argtypes = [ctypes.POINTER(ctypes.c_void_p), wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
for fn in ('midiInPrepareHeader', 'midiInAddBuffer', 'midiInUnprepareHeader', 'midiOutPrepareHeader', 'midiOutLongMsg', 'midiOutUnprepareHeader'):
    getattr(mm, fn).argtypes = [ctypes.c_void_p, ctypes.POINTER(MIDIHDR), wt.UINT]
for fn in ('midiInStart', 'midiInStop', 'midiInReset', 'midiInClose', 'midiOutClose'):
    getattr(mm, fn).argtypes = [ctypes.c_void_p]


def _find(get_num, get_caps, caps_t, name):
    for i in range(get_num()):
        c = caps_t(); get_caps(i, ctypes.byref(c), ctypes.sizeof(c))
        if c.szPname == name:
            return i
    raise KeyError(name)


class Bridge:
    def __init__(self, port='SysEx'):
        self.done = []          # completed sysex messages (bytes)
        self._cb = CB(self._callback)
        self.hin = ctypes.c_void_p()
        r = mm.midiInOpen(ctypes.byref(self.hin), _find(mm.midiInGetNumDevs, mm.midiInGetDevCapsW, INCAPS, port),
                          ctypes.cast(self._cb, ctypes.c_void_p), None, 0x30000)
        assert r == 0, 'midiInOpen %d' % r
        self.bufs = []
        for _ in range(16):
            b = ctypes.create_string_buffer(4096)
            h = MIDIHDR(); h.lpData = ctypes.cast(b, ctypes.c_void_p); h.dwBufferLength = 4096
            mm.midiInPrepareHeader(self.hin, ctypes.byref(h), ctypes.sizeof(h))
            mm.midiInAddBuffer(self.hin, ctypes.byref(h), ctypes.sizeof(h))
            self.bufs.append((b, h))
        mm.midiInStart(self.hin)
        self.alive = True
        threading.Thread(target=self._keep_buffers, daemon=True).start()
        self.hout = ctypes.c_void_p()
        r = mm.midiOutOpen(ctypes.byref(self.hout), _find(mm.midiOutGetNumDevs, mm.midiOutGetDevCapsW, OUTCAPS, port), None, None, 0)
        assert r == 0, 'midiOutOpen %d' % r

    def _callback(self, h, msg, inst, p1, p2):
        if msg == 0x3C4 and p1:            # MIM_LONGDATA: copy the message out, the buffer is recycled later
            hdr = MIDIHDR.from_address(p1)
            if hdr.dwBytesRecorded:
                self.done.append(ctypes.string_at(hdr.lpData, hdr.dwBytesRecorded))

    def _keep_buffers(self):
        while self.alive:
            self._recycle()
            time.sleep(0.003)

    def _recycle(self):
        for b, h in self.bufs:
            if h.dwFlags & 1:              # MHDR_DONE: give the buffer back to the driver
                h.dwFlags &= ~1
                h.dwBytesRecorded = 0
                mm.midiInAddBuffer(self.hin, ctypes.byref(h), ctypes.sizeof(h))

    def send(self, data):
        buf = ctypes.create_string_buffer(bytes(data), len(data))
        h = MIDIHDR(); h.lpData = ctypes.cast(buf, ctypes.c_void_p); h.dwBufferLength = len(data)
        mm.midiOutPrepareHeader(self.hout, ctypes.byref(h), ctypes.sizeof(h))
        mm.midiOutLongMsg(self.hout, ctypes.byref(h), ctypes.sizeof(h))
        for _ in range(200):
            if h.dwFlags & 1:
                break
            time.sleep(0.002)
        mm.midiOutUnprepareHeader(self.hout, ctypes.byref(h), ctypes.sizeof(h))

    def run(self, code, timeout=6.0):
        mid = random.randrange(1, 127)
        data = code.encode('ascii')
        chunks = [data[i:i + 200] for i in range(0, len(data), 200)] or [b'']
        for i, c in enumerate(chunks):
            self.send(bytes([0xF0, 0x7D, 0x01, mid, i, len(chunks)]) + c + bytes([0xF7]))
            time.sleep(0.01)
        parts = {}
        t0 = time.time()
        while time.time() - t0 < timeout:
            self._recycle()
            while self.done:
                m = self.done.pop(0)
                if len(m) >= 7 and m[0] == 0xF0 and m[1] == 0x7D and m[2] == 0x02 and m[3] == mid:
                    parts[m[4]] = (m[5], m[6:-1])
            if parts and len(parts) == next(iter(parts.values()))[0]:
                return b''.join(parts[i][1] for i in range(len(parts))).decode('ascii')
            time.sleep(0.01)
        return 'TIMEOUT'

    def close(self):
        self.alive = False
        time.sleep(0.02)
        mm.midiInStop(self.hin); mm.midiInReset(self.hin)
        for b, h in self.bufs:
            mm.midiInUnprepareHeader(self.hin, ctypes.byref(h), ctypes.sizeof(h))
        mm.midiInClose(self.hin); mm.midiOutClose(self.hout)


if __name__ == '__main__':
    br = Bridge()
    try:
        print(br.run(sys.argv[1]))
    finally:
        br.close()
