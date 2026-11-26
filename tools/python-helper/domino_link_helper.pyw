# Domino Link helper: passes Domino's tempo to FL Studio, and gives Domino a pre-roll.
#
# Tempo: FL Studio 21.0 does not hand MIDI clock to its scripts, so the Domino Link script cannot see
# Domino's tempo itself. This helper listens to Domino's MIDI clock (Domino: Preferences > Sync >
# "Broadcast timing clock"; Domino sends it on all its MIDI-OUT ports), works out the tempo, and sends it
# to the Domino Link script as SysEx (F0 7D 10 bpm*100 in 3 x 7 bit F7) on the loopMIDI "SysEx" port.
#
# Pre-roll: Domino has no setting to start a little before the playhead. When you press Space in Domino,
# the helper makes it start one quantize step (or one bar) earlier, so FL is already running when the
# first note comes; see PREROLL below.
#
# Run it with pythonw (no window) next to Domino; "Domino with FL link.cmd" does both. It quits on its own
# once Domino has been closed for a while, and only one copy runs at a time.
import ctypes, ctypes.wintypes as wt, time, os, sys, collections

CLOCK_PORT = '1'       # loopMIDI port Domino's port A plays into (any Domino port carries the clock)
SCRIPT_PORT = 'SysEx'  # loopMIDI port the Domino Link script listens on (Domino's time code comes in there too)
QUIT_AFTER_S = 15      # quit when Domino has been gone this long
PREROLL = 'quantize'   # Space in Domino starts playback this far before the playhead: 'quantize' = one step of
                       # Domino's quantize setting (e.g. a 16th note), 'bar' = one bar, None = off. Only Space
                       # does this; Domino's Play button, its menu and FL start Domino as before.
LOG = os.path.join(os.environ.get('TEMP', '.'), 'domino_link_helper.log')

mm = ctypes.WinDLL('winmm')
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
u32 = ctypes.WinDLL('user32', use_last_error=True)


def log(*a):
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + ' '.join(str(x) for x in a) + '\n')
    except OSError:
        pass


class MIDIHDR(ctypes.Structure):
    _fields_ = [('lpData', ctypes.c_void_p), ('dwBufferLength', wt.DWORD), ('dwBytesRecorded', wt.DWORD),
                ('dwUser', ctypes.c_void_p), ('dwFlags', wt.DWORD), ('lpNext', ctypes.c_void_p),
                ('reserved', ctypes.c_void_p), ('dwOffset', wt.DWORD), ('dwReserved', ctypes.c_void_p * 8)]


class INCAPS(ctypes.Structure):
    _fields_ = [('wMid', wt.WORD), ('wPid', wt.WORD), ('vDriverVersion', wt.DWORD), ('szPname', wt.WCHAR * 32), ('dwSupport', wt.DWORD)]


class OUTCAPS(ctypes.Structure):
    _fields_ = [('wMid', wt.WORD), ('wPid', wt.WORD), ('vDriverVersion', wt.DWORD), ('szPname', wt.WCHAR * 32),
                ('wTechnology', wt.WORD), ('wVoices', wt.WORD), ('wNotes', wt.WORD), ('wChannelMask', wt.WORD), ('dwSupport', wt.DWORD)]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', wt.DWORD), ('cntUsage', wt.DWORD), ('th32ProcessID', wt.DWORD), ('th32DefaultHeapID', ctypes.c_void_p),
                ('th32ModuleID', wt.DWORD), ('cntThreads', wt.DWORD), ('th32ParentProcessID', wt.DWORD),
                ('pcPriClassBase', ctypes.c_long), ('dwFlags', wt.DWORD), ('szExeFile', wt.WCHAR * 260)]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [('cbSize', wt.DWORD), ('flags', wt.DWORD), ('hwndActive', wt.HWND), ('hwndFocus', wt.HWND),
                ('hwndCapture', wt.HWND), ('hwndMenuOwner', wt.HWND), ('hwndMoveSize', wt.HWND), ('hwndCaret', wt.HWND),
                ('rcCaret', wt.RECT)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wt.WORD), ('wScan', wt.WORD), ('dwFlags', wt.DWORD), ('time', wt.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT), ('pad', ctypes.c_byte * 32)]
    _anonymous_ = ('u',)
    _fields_ = [('type', wt.DWORD), ('u', _U)]


CB = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
for fn in ('midiInOpen', 'midiOutOpen'):
    getattr(mm, fn).argtypes = [ctypes.POINTER(ctypes.c_void_p), wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.DWORD]
for fn in ('midiOutPrepareHeader', 'midiOutLongMsg', 'midiOutUnprepareHeader'):
    getattr(mm, fn).argtypes = [ctypes.c_void_p, ctypes.POINTER(MIDIHDR), wt.UINT]
for fn in ('midiInStart', 'midiInStop', 'midiInClose', 'midiOutClose'):
    getattr(mm, fn).argtypes = [ctypes.c_void_p]
k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
k32.CreateMutexW.restype = wt.HANDLE
k32.OpenProcess.restype = wt.HANDLE
k32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
u32.GetForegroundWindow.restype = wt.HWND
u32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
u32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
u32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
u32.GetGUIThreadInfo.argtypes = [wt.DWORD, ctypes.POINTER(GUITHREADINFO)]
u32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
u32.IsWindow.argtypes = [wt.HWND]
u32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
u32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
u32.PeekMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT, wt.UINT]
u32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]


def device_index(count, get_caps, caps_t, name):
    for i in range(count()):
        c = caps_t(); get_caps(i, ctypes.byref(c), ctypes.sizeof(c))
        if c.szPname == name:
            return i
    return None


def domino_running():
    snap = k32.CreateToolhelp32Snapshot(2, 0)          # TH32CS_SNAPPROCESS
    e = PROCESSENTRY32W(); e.dwSize = ctypes.sizeof(e)
    found = False
    ok = k32.Process32FirstW(snap, ctypes.byref(e))
    while ok:
        if e.szExeFile.lower() == 'domino.exe':
            found = True
            break
        ok = k32.Process32NextW(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return found


class TempoReader:
    """Turns Domino's MIDI clock (24 per quarter note) into a tempo.

    Domino's clock wobbles by about 0.5 ms per tick (not adding up over time). A straight line fitted
    through the tick times gives the tick length; its uncertainty (3 sigma) is about +-0.4 BPM after one
    beat and +-0.05 after four. A whole BPM is preferred whenever it fits, otherwise the tempo is rounded
    to 0.1 BPM. After a change the tempo sent to FL is fine-tuned until it fits over the whole window;
    from then on it only changes when the measurement no longer agrees with it within that uncertainty
    plus 0.1 BPM, or when a whole BPM fits better.

    When Domino jumps to another place while playing, its clock restarts at the new place, so one tick
    comes early (or a little late). Such a tick starts a new piece of the measurement; the line keeps one
    slope across all pieces, so the jump doesn't disturb the tempo."""

    JITTER_S = 0.0006    # wobble of Domino's clock (measured 0.52 ms standard deviation, plus some room)
    STEP_S = 0.0025      # a tick this much longer or shorter than usual is a jump (wobble stays within 2 ms)
    OFF_S = 0.0016       # a tick this far off the line through the ticks before it is a jump too
    WINDOW = 97          # ticks measured over (4 beats)
    FULL_SXX = WINDOW * (WINDOW * WINDOW - 1) / 12.0

    def __init__(self):
        self.reset()

    def reset(self):
        self.pieces = [[]]                           # tick times, split where the clock jumped
        self.intervals = collections.deque(maxlen=5)
        self.last_sent = None                        # send the tempo again on the next play
        self.settled = False

    @staticmethod
    def fit(p):
        """Sums for the least-squares line through the tick times p: sxx, sxy, mean index, mean time."""
        m = len(p)
        mean_i = (m - 1) / 2.0
        mean_t = sum(p) / m
        return m * (m * m - 1) / 12.0, sum((i - mean_i) * (x - mean_t) for i, x in enumerate(p)), mean_i, mean_t

    def jumped(self, piece, now):
        interval = now - piece[-1]
        usual = sorted(self.intervals)[len(self.intervals) // 2] if len(self.intervals) >= 3 else None
        self.intervals.append(interval)
        if usual is not None and abs(interval - usual) > self.STEP_S:
            return True
        if len(piece) >= 24:                         # smaller jumps: compare with the line through this piece
            sxx, sxy, mean_i, mean_t = self.fit(piece)
            return abs(now - (mean_t + sxy / sxx * (len(piece) - mean_i))) > self.OFF_S
        return False

    def feed(self, now):
        piece = self.pieces[-1]
        if piece and now - piece[-1] > 0.25:         # clock stopped in between: Domino stopped and started again
            self.reset()
            piece = self.pieces[-1]
        if piece and self.jumped(piece, now):
            piece = []                               # Domino jumped to another place: start a new piece
            self.pieces.append(piece)
        piece.append(now)
        total = sum(len(p) for p in self.pieces)
        while total > self.WINDOW:                   # measure over the last 4 beats
            del self.pieces[0][0]
            total -= 1
            if not self.pieces[0]:
                del self.pieces[0]
        if total - len(self.pieces) < 24:            # intervals inside the pieces
            return None
        # least-squares slope of tick time over tick number, one slope for all pieces
        sxx = sxy = 0.0
        for p in self.pieces:
            a, b = self.fit(p)[:2]
            sxx += a
            sxy += b
        tick = sxy / sxx
        if len(piece) >= 13 and abs((piece[-1] - piece[-13]) / 12 - tick) > 0.03 * tick:
            self.pieces = [piece[-13:]]              # the tempo changed: measure again from the last 12 ticks
            return None
        bpm = 60.0 / (tick * 24)
        uncertainty = 3 * bpm * self.JITTER_S / sxx ** 0.5 / tick
        whole = round(bpm)
        value = whole if abs(bpm - whole) <= uncertainty else round(bpm, 1)
        last = self.last_sent
        if last is not None:
            off = abs(bpm - last)
            if value == last or off <= uncertainty:
                if sxx >= 0.8 * self.FULL_SXX:
                    self.settled = True              # it fits over (nearly) the whole window: no more fine-tuning
                return None                          # the tempo FL has still fits
            if off <= uncertainty + 0.1 and value != whole and self.settled:
                return None                          # close enough, and no whole BPM to offer
        self.last_sent, self.settled = value, False
        return value


class MtcReader:
    """Domino's MIDI Time Code: collects the 8 quarter-frame pieces and returns the position in ms."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.pieces = [0] * 8
        self.mask = 0
        self.last = -1

    def feed(self, data):
        piece = (data >> 4) & 7
        if piece == 0:
            self.mask = 0
        elif piece != self.last + 1:                 # out of order: wait for the next run
            self.mask = 0
            self.last = piece
            return None
        self.pieces[piece] = data & 15
        self.mask |= 1 << piece
        self.last = piece
        if piece != 7 or self.mask != 0xFF:
            return None
        p = self.pieces
        fps = (24.0, 25.0, 29.97, 30.0)[(p[7] >> 1) & 3]
        hours, minutes, seconds, frames = p[6] | ((p[7] & 1) << 4), p[4] | (p[5] << 4), p[2] | (p[3] << 4), p[0] | (p[1] << 4)
        # piece 7 arrives 7 quarter frames after the frame it describes
        return ((hours * 60 + minutes) * 60 + seconds) * 1000.0 + (frames + 7 / 4.0) * 1000.0 / fps


class Preroll:
    """Space in Domino starts playback a little before the playhead (Domino has no such setting).

    While Domino's main window is the active window, the helper takes Space (a normal Windows hotkey, so no
    other program and no text field in Domino is affected) and sends Domino its own menu commands instead:
    Previous Quantize Unit (or Previous Bar), then Play/Stop. When Domino stops and puts the playhead back
    where playback started (Preferences: "Playhead when stopping playback" = Restart), the helper moves it
    forward again, so the playhead doesn't creep backwards."""

    HOTKEY_ID = 0xD0
    PLAY_STOP = 32886                                       # Domino's Playback menu commands
    BACK = {'quantize': 33326, 'bar': 32895}                # Previous Quantize Unit / Previous Bar
    FORWARD = {'quantize': 33327, 'bar': 32896}             # Next Quantize Unit / Next Bar

    def __init__(self, mode):
        self.mode = mode
        self.registered = False
        self.register_after = 0.0
        self.paths = {}                                     # process id -> exe path
        self.window = None                                  # the Domino window we started with a pre-roll
        self.pending = False                                # that playback hasn't stopped yet
        self.started_at = None
        self.start_pos = None                               # where it started (from the time code), in ms
        self.mtc = MtcReader()

    def exe_path(self, h):
        pid = wt.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value not in self.paths:
            path = ''
            hp = k32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
            if hp:
                buf = ctypes.create_unicode_buffer(1024); size = wt.DWORD(1024)
                if k32.QueryFullProcessImageNameW(hp, 0, buf, ctypes.byref(size)):
                    path = buf.value
                k32.CloseHandle(hp)
            self.paths[pid.value] = path
        return self.paths[pid.value]

    def active_domino(self):
        """Domino's main window if it is the active window."""
        h = u32.GetForegroundWindow()
        if not h:
            return None
        title = ctypes.create_unicode_buffer(512)
        u32.GetWindowTextW(h, title, 512)
        if not title.value.endswith(' - Domino') or not self.exe_path(h).lower().endswith('\\domino.exe'):
            return None
        return h

    @staticmethod
    def typing(h):
        """True while Domino has a text field or a menu open: Space must stay Space there."""
        info = GUITHREADINFO(); info.cbSize = ctypes.sizeof(info)
        if not u32.GetGUIThreadInfo(u32.GetWindowThreadProcessId(h, None), ctypes.byref(info)):
            return False
        if info.flags & 0x1C or info.hwndCaret:            # a menu is open, or a text cursor is showing
            return True
        if info.hwndFocus:
            cls = ctypes.create_unicode_buffer(64)
            u32.GetClassNameW(info.hwndFocus, cls, 64)
            return 'edit' in cls.value.lower() or 'combo' in cls.value.lower()
        return False

    def returns_to_start(self, h):
        """Domino's "Playhead when stopping playback": Restart (1) or Restart without scrolling back (3)."""
        ini = os.path.join(os.path.dirname(self.exe_path(h)), 'IniFiles', os.environ.get('USERNAME', ''), 'System.ini')
        try:
            for line in open(ini, encoding='cp932', errors='replace'):
                if line.strip().startswith('RestTickOnStop='):
                    return line.strip().split('=', 1)[1] in ('1', '3')
        except OSError:
            pass
        return True                                         # Domino's default: Restart

    def update_hotkey(self, now):
        want = self.active_domino() is not None and now >= self.register_after
        if want and not self.registered:
            self.registered = bool(u32.RegisterHotKey(None, self.HOTKEY_ID, 0x4000, 0x20))   # MOD_NOREPEAT, Space
        elif not want and self.registered:
            u32.UnregisterHotKey(None, self.HOTKEY_ID)
            self.registered = False

    def pass_space(self):
        """Space was meant for something else: give it back as a normal key press."""
        if self.registered:
            u32.UnregisterHotKey(None, self.HOTKEY_ID)
            self.registered = False
        keys = (INPUT * 2)()
        for k, flags in ((keys[0], 0), (keys[1], 2)):       # key down, KEYEVENTF_KEYUP
            k.type = 1                                      # INPUT_KEYBOARD
            k.ki.wVk = 0x20
            k.ki.dwFlags = flags
        u32.SendInput(2, keys, ctypes.sizeof(INPUT))
        self.register_after = time.perf_counter() + 0.1     # don't catch our own key press again

    def on_space(self, playing):
        h = self.active_domino()
        if h is None or self.typing(h):
            self.pass_space()
            return
        if playing:
            u32.PostMessageW(h, 0x0111, self.PLAY_STOP, 0)  # WM_COMMAND: stop, as Space does
            return
        if not (self.pending and self.window == h and self.returns_to_start(h)):
            u32.PostMessageW(h, 0x0111, self.BACK[self.mode], 0)   # (else the playhead is still back from last time)
        u32.PostMessageW(h, 0x0111, self.PLAY_STOP, 0)
        self.window, self.pending = h, True
        self.started_at, self.start_pos = time.perf_counter(), None
        self.mtc.reset()

    def on_timecode(self, t, data):
        if self.pending and self.start_pos is None and self.started_at is not None and t >= self.started_at:
            pos = self.mtc.feed(data)
            if pos is not None:
                self.start_pos = pos - (t - self.started_at) * 1000.0

    def on_stopped(self):
        if not self.pending:
            return
        self.pending = False
        h = self.window
        if not h or not u32.IsWindow(h) or not self.returns_to_start(h):
            return
        if self.start_pos is not None and self.start_pos < 20:
            return                                          # it started at the very beginning: nothing was moved back
        u32.PostMessageW(h, 0x0111, self.FORWARD[self.mode], 0)

    def close(self):
        if self.registered:
            u32.UnregisterHotKey(None, self.HOTKEY_ID)
            self.registered = False


def main():
    mutex = k32.CreateMutexW(None, False, 'DominoLinkHelper')
    if ctypes.get_last_error() == 183:     # ERROR_ALREADY_EXISTS: another copy is running
        return
    clocks = collections.deque()
    timecode = collections.deque()

    def on_midi(h, msg, inst, p1, p2):
        if msg == 0x3C3 and ((p1 or 0) & 0xFF) == 0xF8:   # MIM_DATA, timing clock
            clocks.append(time.perf_counter())

    def on_sync(h, msg, inst, p1, p2):
        if msg == 0x3C3 and ((p1 or 0) & 0xFF) == 0xF1:   # MIM_DATA, time code quarter frame
            timecode.append((time.perf_counter(), ((p1 or 0) >> 8) & 0x7F))

    cb, sync_cb = CB(on_midi), CB(on_sync)
    hin = hout = hsync = None
    reader = TempoReader()
    preroll = Preroll(PREROLL) if PREROLL in Preroll.BACK else None
    last_clock = None
    clock_running = False
    msg = wt.MSG()
    gone_since = None
    last_check = 0.0
    log('started')
    while True:
        if hin is None:
            i = device_index(mm.midiInGetNumDevs, mm.midiInGetDevCapsW, INCAPS, CLOCK_PORT)
            o = device_index(mm.midiOutGetNumDevs, mm.midiOutGetDevCapsW, OUTCAPS, SCRIPT_PORT)
            if i is not None and o is not None:
                hin, hout = ctypes.c_void_p(), ctypes.c_void_p()
                if mm.midiInOpen(ctypes.byref(hin), i, ctypes.cast(cb, ctypes.c_void_p), None, 0x30000) or \
                        mm.midiOutOpen(ctypes.byref(hout), o, None, None, 0):
                    log('could not open the loopMIDI ports')
                    hin = hout = None
                else:
                    mm.midiInStart(hin)
                    log('listening on', CLOCK_PORT, 'sending to', SCRIPT_PORT)
                    s = device_index(mm.midiInGetNumDevs, mm.midiInGetDevCapsW, INCAPS, SCRIPT_PORT)
                    hsync = ctypes.c_void_p()
                    if s is None or mm.midiInOpen(ctypes.byref(hsync), s, ctypes.cast(sync_cb, ctypes.c_void_p), None, 0x30000):
                        hsync = None                 # without the time code the pre-roll still works
                    else:
                        mm.midiInStart(hsync)
        while timecode:
            t, data = timecode.popleft()
            if preroll:
                preroll.on_timecode(t, data)
        while clocks:
            last_clock = clocks.popleft()
            clock_running = True
            bpm = reader.feed(last_clock)
            if bpm is not None and hout is not None:
                v = int(round(bpm * 100))
                data = bytes([0xF0, 0x7D, 0x10, (v >> 14) & 0x7F, (v >> 7) & 0x7F, v & 0x7F, 0xF7])
                buf = ctypes.create_string_buffer(data, len(data))
                hdr = MIDIHDR(); hdr.lpData = ctypes.cast(buf, ctypes.c_void_p); hdr.dwBufferLength = len(data)
                mm.midiOutPrepareHeader(hout, ctypes.byref(hdr), ctypes.sizeof(hdr))
                mm.midiOutLongMsg(hout, ctypes.byref(hdr), ctypes.sizeof(hdr))
                for _ in range(100):
                    if hdr.dwFlags & 1:      # MHDR_DONE
                        break
                    time.sleep(0.001)
                mm.midiOutUnprepareHeader(hout, ctypes.byref(hdr), ctypes.sizeof(hdr))
        now_pc = time.perf_counter()
        if clock_running and now_pc - last_clock > 0.25:   # Domino stopped
            clock_running = False
            if preroll:
                preroll.on_stopped()
        if preroll:
            preroll.update_hotkey(now_pc)
            while u32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):   # PM_REMOVE
                if msg.message == 0x0312 and msg.wParam == Preroll.HOTKEY_ID:   # WM_HOTKEY: Space in Domino
                    preroll.on_space(playing=last_clock is not None and now_pc - last_clock < 0.15)
        now = time.time()
        if now - last_check > 5:             # every 5 s: is Domino still open?
            last_check = now
            if domino_running():
                gone_since = None
            elif gone_since is None:
                gone_since = now
            elif now - gone_since > QUIT_AFTER_S:
                break
        time.sleep(0.005)
    if preroll:
        preroll.close()
    if hin is not None:
        mm.midiInStop(hin); mm.midiInClose(hin); mm.midiOutClose(hout)
    if hsync is not None:
        mm.midiInStop(hsync); mm.midiInClose(hsync)
    log('Domino closed, quitting')
    k32.CloseHandle(mutex)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log('error', repr(e))
        sys.exit(1)
