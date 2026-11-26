# Build an FL Studio template whose instrument channels are locked to one or two Domino ports.
#   python make_template.py <port letters, e.g. A or AB> <output .flp>
# Starts from FL's empty project plus 16 (one port) or 32 (two ports) clones of its Sampler, saved by FL 21.0.3
# (template_base.flp / template_base33.flp), and writes:
#   - channel 0 "catcher - keep selected": unlocked, on the master
#   - "<port>01".."<port>16" per port: "Receive notes from" = loopMIDI port N, MIDI channel 1-16,
#     each on its own mixer track with the same name
#   - an "end of song" clip at bar 500 on the last playlist track: without anything in the playlist FL's
#     song position stays at 0, and the Domino Link script could neither read nor set it
# Open the result in FL once and save it into Documents\Image-Line\FL Studio\Projects\Templates\<group>\<name>\<name>.flp.
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flp

LOCK_OFFSET = 116      # in event 215 (channel parameters): int32 port (-2 = not locked), int32 MIDI channel (-1 = all)
MIXER_COLOR = 4866100  # what FL itself writes when it names a mixer track
END_BAR = 500
END_PATTERN = 2
# one playlist clip and one note as FL 21 writes them (positions/ids are filled in below)
CLIP = bytes.fromhex('80040000005001508004000 0f3010000780040004064808 0ffffffffffffffff01000000'.replace(' ', '')) + bytes(24)
NOTE = bytes.fromhex('000000000040000018000000 3c00000078000000406480 80'.replace(' ', ''))

letters, dst = sys.argv[1].upper(), sys.argv[2]
ports = ['ABCDEFGHIJKLMNOP'.index(c) + 1 for c in letters]   # Domino port A-P -> loopMIDI "1"-"16" -> FL port 1-16
here = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(here, 'template_base.flp' if len(ports) == 1 else 'template_base33.flp')
fmt, nch, ppq, evs = flp.load_raw(src)
slots = {}                                                   # channel index -> (port, midi channel 1-16, name)
for k, (letter, port) in enumerate(zip(letters, ports)):
    for n in range(1, 17):
        slots[16 * k + n] = (port, n, '%s%02d drums' % (letter, n) if n == 10 else '%s%02d' % (letter, n))
names = {0: 'catcher - keep selected'}
names.update({i: s[2] for i, s in slots.items()})
assert nch == len(names), 'base project has %d channels, need %d' % (nch, len(names))

bar = 4 * ppq
clip = bytearray(CLIP)
struct.pack_into('<IHHIH', clip, 0, (END_BAR - 1) * bar, 20480, 20480 + END_PATTERN, bar, 0)   # track_rv 0 = track 500
note = bytearray(NOTE)                                        # one short note on the silent catcher
pattern = [(65, END_PATTERN), (193, ('end of song (keep)\0').encode('utf-16-le')), (224, bytes(note))]

out = []
cur = None
named = set()
insert = -1
patterns_added = False
for i, (eid, val) in enumerate(evs):
    if eid == 64 and not patterns_added:                     # patterns come before the first channel
        out += pattern
        patterns_added = True
    if eid == 64:                                            # a new channel block starts
        cur = val
    elif eid == 203 and cur in names and cur not in named:   # channel name
        named.add(cur)
        val = (names[cur] + '\0').encode('utf-16-le')
    elif eid == 215 and cur in names:                        # channel parameters: the MIDI input lock
        v = bytearray(val)
        port, ch = (-2, -1) if cur == 0 else (slots[cur][0], slots[cur][1] - 1)
        struct.pack_into('<ii', v, LOCK_OFFSET, port, ch)
        val = bytes(v)
    elif eid == 22 and cur is not None and insert < 0:       # channel's mixer track
        val = cur if cur in slots else 0
    elif eid == 233:                                         # playlist clips of the arrangement
        val = bytes(val) + bytes(clip)
    elif eid == 42 and i + 1 < len(evs) and evs[i + 1][0] == 236:   # a mixer track block starts
        insert += 1
        cur = None
        if insert in slots and val == 0:
            out += [(149, MIXER_COLOR), (42, 1), (204, (slots[insert][2] + '\0').encode('utf-16-le'))]
            continue
    out.append((eid, val))
assert len(named) == len(names)
flp.save_raw(dst, fmt, nch, ppq, out)
print('wrote', dst, 'ports', ', '.join('%s=%d' % lp for lp in zip(letters, ports)))
