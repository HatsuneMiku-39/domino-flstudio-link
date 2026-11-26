# Measure START_OFFSET_MS: Domino plays the 140 BPM test song (sync_test.mid), FL follows and punches in recording
# once it is running, then the recorded notes are read from the saved project and compared with the beat.
# Needs the test bridge, FL open on a test project with channels locked to port 1 channels 1 and 2, and the test
# song open in Domino.
#   python offset_test.py <the project open in FL>
# Late notes (+) mean START_OFFSET_MS is too big by that much; early notes (-) mean it is too small.
# FL's main snap is switched off during the test: with "quantize note start time" on (Recording options), FL snaps
# recorded notes to it and would hide the error.
import sys, os, time, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fl import Bridge

project = sys.argv[1]
BPM, PPQ = 140.0, 96
EXPECTED = {67: [0, 1], 60: list(range(4, 12)), 64: [b + 0.5 for b in range(4, 12)]}   # key -> beats


def notes(path, pattern):
    b = open(path, 'rb').read()
    p = 8 + struct.unpack_from('<I', b, 4)[0] + 8
    cur, out = None, []
    while p < len(b):
        eid = b[p]; p += 1
        if eid < 64: val = b[p]; p += 1
        elif eid < 128: val = struct.unpack_from('<H', b, p)[0]; p += 2
        elif eid < 192: val = struct.unpack_from('<I', b, p)[0]; p += 4
        else:
            n = shift = 0
            while True:
                c = b[p]; p += 1; n |= (c & 0x7F) << shift; shift += 7
                if not c & 0x80: break
            val = b[p:p + n]; p += n
        if eid == 65: cur = val
        elif eid == 64: cur = None
        elif eid == 224 and cur == pattern:
            for i in range(0, len(val) - 23, 24):
                pos, _f, rack, length, key = struct.unpack_from('<IHHIH', val, i)
                out.append((pos, key, rack))
    return out


br = Bridge()
try:
    print(br.run("G['snap_before'] = ui.getSnapMode()\nui.setSnapMode(midi.Snap_None)\n"
                 "ui.showWindow(midi.widPlaylist)\nui.setFocused(midi.widPlaylist)\n"
                 "patterns.findFirstNextEmptyPat(midi.FFNEP_DontPromptName)\n"
                 "G['offset_pattern'] = patterns.patternNumber()\n"
                 "transport.setSongPos(0, midi.SONGLENGTH_ABSTICKS)\n"
                 "out('pattern', patterns.patternNumber(), 'snap', ui.getSnapMode(), 'tempo', mixer.getCurrentTempo())"))
    pattern = int(br.run("out(G['offset_pattern'])"))
    br.send([0xF0, 0x7F, 0x7F, 0x06, 0x44, 0x06, 0x01, 0x60, 0, 0, 0, 0, 0xF7])   # Domino: locate to 0, play
    br.send([0xF0, 0x7F, 0x7F, 0x06, 0x02, 0xF7])
    time.sleep(1.2)
    print(br.run("transport.record()\nout('punched in at', transport.getSongPosHint(), 'state', link.state, 'recording', transport.isRecording())"))
    time.sleep(5.0)
    print(br.run("out('state', link.state, 'playing', transport.isPlaying())\n"
                 "if transport.isRecording():\n    transport.record()\n"
                 "transport.globalTransport(midi.FPT_Save, 1)\nout('saved')"))
finally:
    print(br.run("ui.setSnapMode(G.get('snap_before', ui.getSnapMode()))\nout('snap back to', ui.getSnapMode())"))
    br.close()
time.sleep(1.0)
tick_ms = 60000.0 / (BPM * PPQ)
devs = []
for pos, key, rack in sorted(notes(project, pattern)):
    beats = EXPECTED.get(key)
    if not beats:
        continue
    beat = min(beats, key=lambda x: abs(pos - x * PPQ))
    if beat < 4:
        continue                             # before the punch-in
    devs.append((pos - beat * PPQ) * tick_ms)
    print('  key %d at beat %5.2f: %+6.1f ms' % (key, beat, devs[-1]))
if devs:
    mean = sum(devs) / len(devs)
    print('%d notes, mean %+.1f ms (late is +), min %+.1f, max %+.1f' % (len(devs), mean, min(devs), max(devs)))
else:
    print('no notes recorded in pattern', pattern)
