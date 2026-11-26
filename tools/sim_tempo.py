# Synthetic tests for the helper's TempoReader: Domino-like clock (0.5 ms wobble, max 1.5 ms) with tempo changes,
# stops and jumps. Prints what the reader would send to FL.
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from replay_tempo import helper, OldReader

random.seed(7)


def wobble():
    return max(-0.0015, min(0.0015, random.gauss(0, 0.00052)))


def clock(plan):
    """plan: list of ('play', bpm, seconds) / ('stop', seconds) / ('jump',) / ('ramp', bpm_from, bpm_to, seconds)."""
    ts, t, grid = [], 100.0, 100.0
    for step in plan:
        if step[0] == 'stop':
            grid += step[1]; continue
        if step[0] == 'jump':
            grid = ts[-1] + random.uniform(0.0005, 60.0 / (140 * 24)) if ts else grid; continue
        if step[0] == 'play':
            bpm, secs = step[1], step[2]
            end = grid + secs
            while grid < end:
                ts.append(grid + wobble()); grid += 60.0 / (bpm * 24)
        if step[0] == 'ramp':
            a, b, secs = step[1], step[2], step[3]
            start = grid
            while grid < start + secs:
                bpm = a + (b - a) * (grid - start) / secs
                ts.append(grid + wobble()); grid += 60.0 / (bpm * 24)
    return ts


def show(label, plan, readers=('new',)):
    ts = clock(plan)
    for name in readers:
        r = helper.TempoReader() if name == 'new' else OldReader()
        out = []
        for t in ts:
            b = r.feed(t)
            if b is not None:
                out.append((round(t - ts[0], 2), b))
        print('%-34s %s: %s' % (label, name, out if len(out) <= 12 else '%d sends %s ...' % (len(out), out[:12])))


jumps = []
for k in range(30):
    jumps += [('play', 140, random.uniform(0.3, 2.0)), ('jump',)]
show('steady 140, 20 s', [('play', 140, 20)])
show('steady 97.5, 10 s', [('play', 97.5, 10)])
show('97.5, stop, 140', [('play', 97.5, 3), ('stop', 1), ('play', 140, 3)])
show('140 -> 120 while playing', [('play', 140, 4), ('play', 120, 4)])
show('140 -> 150 while playing', [('play', 140, 4), ('play', 150, 4)])
show('140 -> 141 while playing', [('play', 140, 4), ('play', 141, 4)])
show('140 -> 139.5 while playing', [('play', 140, 4), ('play', 139.5, 6)])
show('128.6 steady', [('play', 128.6, 8)])
show('128.65 steady 30 s', [('play', 128.65, 30)])
show('140 steady 60 s', [('play', 140, 60)])
show('ramp 120 -> 140 over 4 s', [('play', 120, 2), ('ramp', 120, 140, 4), ('play', 140, 3)])
show('300 BPM', [('play', 300, 6)])
show('40 BPM', [('play', 40, 12)])
show('40 -> 42 while playing', [('play', 40, 8), ('play', 42, 8)])
show('30 jumps at 140', jumps, ('old', 'new'))
show('jumps then 140 -> 110', jumps[:10] + [('play', 110, 4)])
