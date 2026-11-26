# Feed recorded Domino clock times through the old and the new tempo reader and show what each would send to FL.
#   python replay_tempo.py <recording.json> [<recording.json> ...]
import sys, os, json, importlib.machinery, importlib.util

HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'python-helper', 'domino_link_helper.pyw')
loader = importlib.machinery.SourceFileLoader('helper', HELPER)
spec = importlib.util.spec_from_loader('helper', loader)
helper = importlib.util.module_from_spec(spec); loader.exec_module(helper)


class OldReader:
    JITTER_S = 0.00075

    def __init__(self):
        self.times = []; self.last_sent = None

    def feed(self, now):
        t = self.times
        if t and now - t[-1] > 0.25:
            del t[:]; self.last_sent = None
        t.append(now)
        if len(t) > 97: del t[0]
        n = len(t) - 1
        if n >= 24:
            recent = (t[-1] - t[-13]) / 12; overall = (t[-1] - t[0]) / n
            if abs(recent - overall) > 0.03 * overall:
                del t[:-13]; return None
        if n < 24: return None
        m = len(t); mean_i = (m - 1) / 2.0; mean_t = sum(t) / m
        tick = sum((i - mean_i) * (x - mean_t) for i, x in enumerate(t)) / sum((i - mean_i) ** 2 for i in range(m))
        bpm = 60.0 / (tick * 24)
        unc = 3 * bpm * self.JITTER_S * (12.0 / (m * (m * m - 1))) ** 0.5 / tick
        if self.last_sent is not None and abs(bpm - self.last_sent) <= unc + 0.1: return None
        whole = round(bpm)
        bpm = whole if abs(bpm - whole) <= unc else round(bpm, 1)
        if self.last_sent is not None and abs(bpm - self.last_sent) < 0.05: return None
        self.last_sent = bpm; return bpm


def replay(reader, ts):
    out = []
    for t in ts:
        b = reader.feed(t)
        if b is not None:
            out.append((round(t - ts[0], 2), b))
    return out


if __name__ == '__main__':
    for path in sys.argv[1:]:
        ts = json.load(open(path))['clocks']
        print(path.split('/')[-1], len(ts), 'clocks')
        for name, R in (('old', OldReader), ('new', helper.TempoReader)):
            out = replay(R(), ts)
            print('  %s sent %d: %s%s' % (name, len(out), out[:14], ' ...' if len(out) > 14 else ''))
