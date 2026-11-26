# Minimal FL Studio .flp reader for the Domino -> FL tests: channels, patterns, notes, controller events.
#   python flp.py <project.flp> [--events]
import sys, struct, collections

BYTE, WORD, DWORD, TEXT, DATA = 0, 64, 128, 192, 208
CH_NEW, PAT_NEW = 64, 65
CH_DEFNAME, NAME = 201, 203
PAT_CTRL, PAT_NOTES = 223, 224
TEMPO = 156


def events(path):
    b = open(path, 'rb').read()
    assert b[:4] == b'FLhd', 'not an FLP file'
    hlen = struct.unpack_from('<I', b, 4)[0]
    fmt, nch, ppq = struct.unpack_from('<hHH', b, 8)
    p = 8 + hlen
    assert b[p:p + 4] == b'FLdt'
    end = p + 8 + struct.unpack_from('<I', b, p + 4)[0]
    p += 8
    out = []
    while p < end:
        eid = b[p]; p += 1
        if eid < WORD:
            val = b[p]; p += 1
        elif eid < DWORD:
            val = struct.unpack_from('<H', b, p)[0]; p += 2
        elif eid < TEXT:
            val = struct.unpack_from('<I', b, p)[0]; p += 4
        else:
            n = 0; shift = 0
            while True:
                c = b[p]; p += 1
                n |= (c & 0x7F) << shift; shift += 7
                if not c & 0x80:
                    break
            val = b[p:p + n]; p += n
        out.append((eid, val))
    return ppq, out


def load_raw(path):
    """(format, channel count, ppq, [(id, value), ...]) for rewriting a project"""
    b = open(path, 'rb').read()
    fmt, nch, ppq = struct.unpack_from('<hHH', b, 8)
    return fmt, nch, ppq, events(path)[1]


def save_raw(path, fmt, nch, ppq, evs):
    out = bytearray()
    for eid, val in evs:
        out.append(eid)
        if eid < WORD:
            out.append(val)
        elif eid < DWORD:
            out += struct.pack('<H', val)
        elif eid < TEXT:
            out += struct.pack('<I', val)
        else:
            n = len(val)
            while True:
                c = n & 0x7F; n >>= 7
                out.append(c | (0x80 if n else 0))
                if not n:
                    break
            out += val
    data = b'FLhd' + struct.pack('<IhHH', 6, fmt, nch, ppq) + b'FLdt' + struct.pack('<I', len(out)) + bytes(out)
    open(path, 'wb').write(data)


def text(v):
    try:
        return v.decode('utf-16-le').rstrip('\0')
    except Exception:
        return v.decode('latin-1').rstrip('\0')


def read(path):
    ppq, evs = events(path)
    chans = collections.OrderedDict()   # iid -> {'plugin':..., 'name':...}
    pats = collections.OrderedDict()    # pattern number -> {'notes': [...], 'ctrl': [...], 'name':...}
    cur_ch = cur_pat = None
    tempo = None
    for eid, v in evs:
        if eid == CH_NEW:
            cur_ch = v; chans.setdefault(v, {'plugin': '', 'name': ''}); cur_pat = None
        elif eid == PAT_NEW:
            cur_pat = v; pats.setdefault(v, {'notes': [], 'ctrl': [], 'name': ''}); cur_ch = None
        elif eid == TEMPO:
            tempo = v / 1000.0
        elif eid == CH_DEFNAME and cur_ch is not None:
            chans[cur_ch]['plugin'] = text(v)
        elif eid == NAME and cur_ch is not None:
            chans[cur_ch]['name'] = text(v)
        elif eid == 193 and cur_pat is not None:
            pats[cur_pat]['name'] = text(v)
        elif eid == PAT_NOTES and cur_pat is not None:
            for i in range(0, len(v) - 23, 24):
                pos, flags, rack, length, key, group, fine, _u, rel, mch, pan, vel, mx, my = struct.unpack_from('<IHHIHHBBBBBBBB', v, i)
                pats[cur_pat]['notes'].append(dict(pos=pos, len=length, key=key, chan=rack, midi=mch, vel=vel, pan=pan, fine=fine))
        elif eid == PAT_CTRL and cur_pat is not None:
            for i in range(0, len(v) - 11, 12):
                pos, _u1, _u2, ch, fl, val = struct.unpack_from('<IBBBBf', v, i)
                pats[cur_pat]['ctrl'].append(dict(pos=pos, chan=ch, flags=fl, value=val))
    return dict(ppq=ppq, tempo=tempo, chans=chans, pats=pats, events=evs)


NOTE_NAMES = 'C C# D D# E F F# G G# A A# B'.split()
def keyname(k):
    return '%s%d' % (NOTE_NAMES[k % 12], k // 12)   # FL: key 60 = C5


if __name__ == '__main__':
    r = read(sys.argv[1])
    print('PPQ %d  tempo %s' % (r['ppq'], r['tempo']))
    for iid, c in r['chans'].items():
        print('channel %d: %r (%s)' % (iid, c['name'], c['plugin']))
    for n, p in r['pats'].items():
        if not p['notes'] and not p['ctrl']:
            continue
        print('pattern %d %r: %d notes, %d controller events' % (n, p['name'], len(p['notes']), len(p['ctrl'])))
        for x in sorted(p['notes'], key=lambda x: (x['pos'], x['chan'])):
            c = r['chans'].get(x['chan'], {})
            print('   pos %6d (beat %7.3f)  len %4d  %-4s chan %d %-12r midi-color %d vel %d' % (
                x['pos'], x['pos'] / r['ppq'], x['len'], keyname(x['key']), x['chan'], c.get('name') or c.get('plugin'), x['midi'], x['vel']))
        for x in p['ctrl'][:60]:
            print('   ctrl pos %6d chan %d flags %d value %.4f' % (x['pos'], x['chan'], x['flags'], x['value']))
    if '--events' in sys.argv:
        for eid, v in r['events']:
            print(eid, v if not isinstance(v, bytes) else (v[:40].hex() + ('...' if len(v) > 40 else '')))
