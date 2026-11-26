# name=Domino Link
# supportedDevices=SysEx,Domino Link
# Domino Link for FL Studio
#
# Makes FL Studio follow the Domino MIDI editor, the way Cubase does:
#   * press Play in Domino  -> FL starts at the same song position
#   * move Domino's playhead while playing -> FL jumps along
#   * press Stop in Domino  -> FL stops
#   * press Play/Stop in FL -> Domino starts/stops too (needs Domino's MMC slave)
#   * move FL's playhead while playing -> Domino jumps along
#   * FL takes over Domino's tempo (needs Domino's "Broadcast timing clock" and the Domino Link add-on
#     version.dll next to Domino.exe, because FL 21.0 does not pass MIDI clock to scripts)
#   * without Domino, FL plays as if this script weren't there
#   * on Domino's instrument ports, controllers and pitch bend reach the FL instrument whose mixer
#     track (or channel) is named after the Domino port and channel, e.g. "A01" or "B10 drums"
# Because FL really runs its transport, FL can record what Domino plays.
#
# How it works: Domino sends MIDI Time Code (MTC) while it plays
# (Domino: Preferences > Sync > "Enable MTC Master"). This script reads that
# time code. Domino never sends Start/Stop/Song Position messages, so a stop
# is detected when the time code goes quiet.
#
# Setup (FL Studio: Options > MIDI settings):
#   Input  "SysEx" (the loopMIDI port Domino's MTC goes to):
#          Enable it, Controller type = "Domino Link (user)", Port = 17
#   Output "SysEx": Port = 17, "Send master sync" OFF
#   Inputs "1".."16" (Domino's ports A..P): Controller type = "Domino Link (user)", Port = 1..16
# See the README.md that comes with this script for the full walkthrough.

import midi
import transport
import device
import ui
import general
import channels
import plugins
import mixer

try:
    import time
    _clock = time.perf_counter
except Exception:  # FL's embedded Python normally has time; fall back just in case
    _clock = None

# ---------------------------------------------------------------- settings --
STOP_TIMEOUT_MS = 200      # time code silent this long = Domino stopped
JUMP_THRESHOLD_MS = 120    # time code jumping more than this = playhead moved
START_OFFSET_MS = 50       # FL records live notes this much too early (measured with Voicemeeter Virtual ASIO, 48 kHz, 1056 samples)
ALIGN_TO_DOMINO = True     # if Domino starts while FL already plays, nudge FL onto Domino's exact position
FORCE_SONG_MODE = True     # switch FL to Song mode when Domino starts it
DISABLE_COUNTDOWN = True   # turn off FL's record countdown (it would break sync)
CONTROL_DOMINO = True      # FL Play/Stop also starts/stops Domino via MMC
FOLLOW_FL_JUMPS = True     # moving FL's playhead while playing moves Domino too
FL_JUMP_THRESHOLD_MS = 250 # FL's position jumping more than this = playhead moved in FL
FOLLOW_TEMPO = True        # take over the tempo the Domino add-on reads from Domino's MIDI clock
FORWARD_CONTROLLERS = True # instrument ports: controllers/pitch bend go to the matching FL instrument
MMC_DEVICE_ID = 0x7F       # 0x7F = all devices (Domino's default is 127)
MMC_FPS = 30               # frame rate used for MMC locate messages (Domino ignores sub-frames)
SHOW_HINTS = True          # status text in FL's hint bar

PASS_CC = (64, 120, 123)   # left to FL: sustain ("Foot pedal controls note off"), sound off, all notes off
DROP_CC = (0, 6, 32, 38, 96, 97, 98, 99, 100, 101)  # bank select and RPN/NRPN: never forwarded
CC_PARAM = 4096            # FL's VST wrapper exposes "MIDI CC #0..#127" as parameters 4096..4223
AFTERTOUCH_PARAM = 4224    # ... and "MIDI Channel 1 Aftertouch" as 4224

IDLE, FOLLOW, LEAD = 'idle', 'follow', 'lead'


def timecode_to_ms(hours, minutes, seconds, frames, rate):
    """MTC rate code: 0=24, 1=25, 2=29.97 drop-frame, 3=30 fps."""
    if rate == 2:
        total_minutes = 60 * hours + minutes
        frame_no = (108000 * hours + 1800 * minutes + 30 * seconds + frames
                    - 2 * (total_minutes - total_minutes // 10))
        return frame_no * 1000.0 / 29.97
    fps = (24, 25, 30, 30)[rate]
    return ((hours * 60 + minutes) * 60 + seconds) * 1000.0 + frames * 1000.0 / fps


class MtcReader:
    """Collects the 8 quarter-frame pieces and returns the position in ms."""

    FPS = (24.0, 25.0, 29.97, 30.0)

    def __init__(self):
        self.reset()

    def reset(self):
        self.pieces = [0] * 8
        self.mask = 0
        self.last_piece = -1

    def feed(self, data1):
        piece = (data1 >> 4) & 7
        if piece == 0:
            self.mask = 0
        elif piece != self.last_piece + 1:
            # out of order (Domino always starts a run at piece 0); wait for the next run
            self.mask = 0
            self.last_piece = piece
            return None
        self.pieces[piece] = data1 & 0x0F
        self.mask |= 1 << piece
        self.last_piece = piece
        if piece != 7 or self.mask != 0xFF:
            return None
        self.mask = 0
        p = self.pieces
        rate = (p[7] >> 1) & 3
        ms = timecode_to_ms(p[6] | ((p[7] & 1) << 4), p[4] | (p[5] << 4),
                            p[2] | (p[3] << 4), p[0] | (p[1] << 4), rate)
        # piece 7 arrives 7 quarter-frames after the frame it describes
        return ms + 7 * 1000.0 / (4 * self.FPS[rate])


def fl_bpm():
    return mixer.getCurrentTempo() / 1000.0


class Link:
    def __init__(self, clock):
        self.clock = clock
        self.mtc = MtcReader()
        self.state = IDLE
        self.last_seen = None        # wall time of the last time code / clock byte
        self.last_pos = None         # last Domino position (ms) and when it arrived
        self.last_pos_time = None
        self.fl_playing = False
        self.expected_playing = None  # FL play state we caused ourselves
        self.wait_for_silence = False # ignore Domino until its time code stops
        self.align_pending = False
        self.fl_ref = None           # FL position (ms) and when it was read, to notice jumps made in FL
        self.ignore_fl_until = 0.0   # FL position changes before this time are our own
        self.tempo_seen = mixer.getCurrentTempo()
        self.started_at = None       # when the current play started (FL's tempo may still be catching up)

    # ---------------------------------------------------------- helpers --
    def hint(self, text):
        if SHOW_HINTS:
            try:
                ui.setHintMsg('Domino Link: ' + text)
            except Exception:
                pass

    # FL's own ms position ignores tempo changes made by scripts, so positions go through ticks and the
    # current tempo (the same as Domino's once the tempo is synced; one tempo for the whole song)
    def fl_ms(self):
        return transport.getSongPos(midi.SONGLENGTH_ABSTICKS) * 60000.0 / (general.getRecPPQ() * fl_bpm())

    def set_fl_pos(self, ms):
        ticks = (ms + START_OFFSET_MS) * fl_bpm() * general.getRecPPQ() / 60000.0
        transport.setSongPos(max(0, int(round(ticks))), midi.SONGLENGTH_ABSTICKS)
        self.fl_ref = None
        self.ignore_fl_until = self.clock() + 0.1

    def start_fl(self, pos_ms):
        if FORCE_SONG_MODE and transport.getLoopMode() == 0:
            transport.setLoopMode()
        if DISABLE_COUNTDOWN and transport.isRecording():
            try:
                if ui.isPrecountEnabled():
                    transport.globalTransport(midi.FPT_CountDown, 1)
            except Exception:
                pass
        self.set_fl_pos(pos_ms)
        if not transport.isPlaying():
            self.expected_playing = True
            transport.start()
        self.fl_playing = True
        self.started_at = self.clock()
        self.hint('following Domino from %s' % fmt_ms(pos_ms))

    def stop_fl(self):
        if transport.isPlaying():
            self.expected_playing = False
            transport.stop()
        self.fl_playing = False

    def send_mmc(self, *data):
        if not CONTROL_DOMINO:
            return
        try:
            if device.isAssigned():
                device.midiOutSysex(bytes([0xF0, 0x7F, MMC_DEVICE_ID, 0x06] + list(data) + [0xF7]))
        except Exception:
            pass

    def mmc_locate(self, ms):
        """Point Domino at ms; returns the time actually sent (whole frames: Domino ignores sub-frames)."""
        frames = int(round(max(0.0, ms) * MMC_FPS / 1000.0))
        fr = frames % MMC_FPS
        secs = frames // MMC_FPS
        hr, mn, sc = secs // 3600, (secs // 60) % 60, secs % 60
        rate_bits = {24: 0, 25: 1, 30: 3}.get(MMC_FPS, 3) << 5
        self.send_mmc(0x44, 0x06, 0x01, (hr & 0x1F) | rate_bits, mn, sc, fr, 0)
        return frames * 1000.0 / MMC_FPS

    def forget_position(self):
        self.mtc.reset()
        self.last_pos = None
        self.last_pos_time = None

    # ------------------------------------------------------ MIDI input --
    def on_quarter_frame(self, data1):
        now = self.clock()
        self.last_seen = now
        pos = self.mtc.feed(data1)
        if pos is None or self.wait_for_silence:
            return
        if self.state == IDLE:
            if transport.isPlaying():
                # FL was already running (started by hand) - treat FL as the leader
                self.state = LEAD
                self.align_pending = ALIGN_TO_DOMINO
            else:
                self.state = FOLLOW
                self.start_fl(pos)
                self.remember(pos, now)
                return
        if self.align_pending:
            self.align_pending = False
            if abs(self.fl_ms() - (pos + START_OFFSET_MS)) > 15:
                self.set_fl_pos(pos)
        elif self.last_pos is not None:
            expected = self.last_pos + (now - self.last_pos_time) * 1000.0
            if abs(pos - expected) > JUMP_THRESHOLD_MS:
                self.set_fl_pos(pos)
                self.hint('jumped to %s' % fmt_ms(pos))
        self.remember(pos, now)

    def remember(self, pos, now):
        self.last_pos = pos
        self.last_pos_time = now

    def on_clock(self):
        self.last_seen = self.clock()

    def on_full_frame(self, sysex):
        # F0 7F <dev> 01 01 hr mn sc fr F7 - only used to follow jumps while playing
        if len(sysex) < 10 or self.state == IDLE or self.wait_for_silence:
            return
        hr = sysex[5]
        pos = timecode_to_ms(hr & 0x1F, sysex[6], sysex[7], sysex[8], (hr >> 5) & 3)
        self.set_fl_pos(pos)
        self.remember(pos, self.clock())

    # ----------------------------------------------------------- polling --
    def on_idle(self):
        now = self.clock()
        playing = transport.isPlaying()

        tempo = mixer.getCurrentTempo()
        if tempo != self.tempo_seen:
            # positions in ms are computed with the new tempo now: not a jump made in FL
            self.tempo_seen = tempo
            self.fl_ref = None
            self.ignore_fl_until = now + 0.15
            if self.state != IDLE and self.started_at is not None and now - self.started_at < 2.0:
                # FL only just took over Domino's tempo: place it again with that tempo, once per start
                self.started_at = None
                self.align_pending = True

        if self.last_seen is not None and (now - self.last_seen) * 1000.0 > STOP_TIMEOUT_MS:
            # Domino's time code went quiet: Domino stopped
            self.last_seen = None
            self.forget_position()
            if self.wait_for_silence:
                self.wait_for_silence = False
            elif self.state in (FOLLOW, LEAD):
                self.state = IDLE
                if playing:
                    self.stop_fl()
                    playing = False
                self.hint('Domino stopped')

        if playing != self.fl_playing:
            if self.expected_playing is not None and playing == self.expected_playing:
                pass  # our own start/stop
            elif playing:
                # Play pressed in FL: let Domino follow from FL's position. FL's playhead stays where it
                # is; only when Domino answers with its time code is FL put the recording offset ahead
                # of it. Without Domino, FL plays exactly as it would without this script.
                self.state = LEAD
                self.align_pending = True
                self.forget_position()
                self.mmc_locate(self.fl_ms() - START_OFFSET_MS)
                self.send_mmc(0x02)
                self.started_at = now
            else:
                # Stop pressed in FL
                if self.state != IDLE:
                    self.send_mmc(0x01)
                    self.wait_for_silence = self.last_seen is not None
                self.state = IDLE
                self.forget_position()
            self.expected_playing = None
            self.fl_playing = playing
            self.fl_ref = None

        if FOLLOW_FL_JUMPS and playing and self.state in (FOLLOW, LEAD) and not self.wait_for_silence:
            pos = self.fl_ms()
            if self.fl_ref is not None and now > self.ignore_fl_until:
                expected = self.fl_ref[0] + (now - self.fl_ref[1]) * 1000.0
                if abs(pos - expected) > FL_JUMP_THRESHOLD_MS:
                    # the playhead was moved in FL: take Domino along (FL is lined up once Domino answers)
                    sent = self.mmc_locate(pos - START_OFFSET_MS)
                    self.forget_position()
                    self.align_pending = True
                    self.fl_ref = None
                    self.ignore_fl_until = now + 0.1
                    self.hint('Domino jumped to %s' % fmt_ms(sent))
                    return
            self.fl_ref = (pos, now)


class PortRouter:
    """An instrument port (Domino port A..P = FL port 1..16): send controllers to the right instrument.
    Notes are left to FL, which routes them with the channels' "Receive notes from" locks."""

    def __init__(self, port, clock):
        self.port = port
        self.clock = clock
        self.slots = {}              # MIDI channel 1..16 -> FL channel index
        self.built = -10.0

    def rebuild(self):
        slots = {}
        for i in range(channels.channelCount()):
            s = slot_of(mixer.getTrackName(channels.getTargetFxTrack(i))) or slot_of(channels.getChannelName(i))
            if s and s[0] == self.port and s[1] not in slots:
                slots[s[1]] = i
        self.slots = slots
        self.built = self.clock()

    def on_idle(self):
        if self.clock() - self.built > 2.0:
            self.rebuild()

    def target(self, midi_channel):
        idx = self.slots.get(midi_channel)
        if idx is None or idx >= channels.channelCount():
            return None
        return idx

    def on_midi(self, event):
        kind = event.status & 0xF0
        if kind in (0x80, 0x90):
            return                       # notes: FL's channel locks route them
        if kind == 0xB0 and event.data1 in PASS_CC:
            return
        event.handled = True
        if kind == 0xB0 and event.data1 in DROP_CC or kind in (0xA0, 0xC0):
            return                       # bank/RPN, polyphonic aftertouch, program change: not forwarded
        idx = self.target((event.status & 0x0F) + 1)
        if idx is None or not plugins.isValid(idx):
            return
        rec = channels.getRecEventId(idx)
        flags = midi.REC_MIDIController  # like a linked controller: FL records it as automation
        if kind == 0xB0:
            general.processRECEvent(rec + midi.REC_Chan_Plugin_First + CC_PARAM + event.data1,
                                    event.data2 * midi.FromMIDI_Max // 127, flags)
        elif kind == 0xD0:
            general.processRECEvent(rec + midi.REC_Chan_Plugin_First + AFTERTOUCH_PARAM,
                                    event.data1 * midi.FromMIDI_Max // 127, flags)
        elif kind == 0xE0:
            # FL's channel pitch spans -4800..+4800 cents; the channel's bend range (2 semitones unless
            # changed) is what a full pitch bend means, and FL hands it to the VST as MIDI pitch bend
            bend = ((event.data1 | (event.data2 << 7)) - 8192) / 8192.0
            cents = bend * channels.getChannelPitch(idx, 2) * 100
            general.processRECEvent(rec + midi.REC_Chan_Pitch, int((cents + 4800) / 9600 * midi.FromMIDI_Max), flags)


def slot_of(name):
    """'A01' / 'B10 drums' -> (port 1..16, MIDI channel 1..16)"""
    name = (name or '').strip()
    if len(name) >= 3 and 'A' <= name[0].upper() <= 'P' and name[1:3].isdigit() \
            and (len(name) == 3 or not name[3].isdigit()):
        ch = int(name[1:3])
        if 1 <= ch <= 16:
            return ord(name[0].upper()) - 64, ch
    return None


def fmt_ms(ms):
    ms = max(0, int(ms))
    return '%d:%02d.%03d' % (ms // 60000, (ms // 1000) % 60, ms % 1000)


# ------------------------------------------------------------ FL callbacks --
_link = None
_router = None
_ticks = [0]


def _tick_clock():
    # fallback clock if the time module is missing: OnIdle runs roughly every 20 ms
    return _ticks[0] * 0.02


def OnInit():
    global _link, _router
    port = device.getPortNumber()
    if 1 <= port <= 16 and device.getName() != 'SysEx':
        # one of Domino's instrument ports
        if FORWARD_CONTROLLERS:
            _router = PortRouter(port, _clock or _tick_clock)
            _router.rebuild()
        return
    _link = Link(_clock or _tick_clock)
    _link.fl_playing = transport.isPlaying()
    try:
        # FL's own master sync on this port would loop back through loopMIDI
        # and look like Domino playing, so make sure it is off
        if device.getMasterSync():
            device.setMasterSync(False)
    except Exception:
        pass
    _link.hint('ready (listening on port %d)' % port)


def OnDeInit():
    global _link, _router
    _link = None
    _router = None


def OnMidiIn(event):
    if _router is not None:
        _router.on_midi(event)
        return
    if _link is None:
        return
    status = event.status
    if status == 0xF1:                      # MTC quarter frame
        _link.on_quarter_frame(event.data1)
        event.handled = True
    elif status == 0xF8:                    # MIDI clock (FL 21.0 does not pass it to scripts anyway)
        _link.on_clock()
        event.handled = True
    elif status in (0xFA, 0xFB, 0xFC, 0xF2, 0xFE):
        event.handled = True                # Domino does not send these; ignore if others do
    elif status == 0xF0:
        sysex = event.sysex or b''
        if len(sysex) >= 7 and sysex[1] == 0x7D and sysex[2] == 0x10:
            # tempo from the Domino add-on (it reads Domino's MIDI clock): F0 7D 10 bpm*100 (3 x 7 bit) F7
            if FOLLOW_TEMPO:
                bpm100 = (sysex[3] << 14) | (sysex[4] << 7) | sysex[5]
                general.processRECEvent(midi.REC_Tempo, bpm100 * 10, midi.REC_UpdateValue | midi.REC_UpdateControl)
            event.handled = True
        elif len(sysex) >= 5 and sysex[1] == 0x7F and sysex[3] == 0x01 and sysex[4] == 0x01:
            _link.on_full_frame(sysex)
            event.handled = True
        elif len(sysex) >= 4 and sysex[1] == 0x7F and sysex[3] == 0x06:
            event.handled = True            # our own MMC coming back through loopMIDI
        elif len(sysex) >= 4 and sysex[1] == 0x7E and sysex[3] == 0x06:
            event.handled = True            # identity request Domino sends at startup


def OnIdle():
    _ticks[0] += 1
    if _link is not None:
        _link.on_idle()
    elif _router is not None:
        _router.on_idle()
