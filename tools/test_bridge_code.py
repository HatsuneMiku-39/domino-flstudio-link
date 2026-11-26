# The test bridge that tools\make_test_build.py adds to the FL script (not a script of its own).
# ------------------------------------------------- TEMPORARY TEST BRIDGE --
_bridge = {'parts': {}}


def _bridge_sysex(sx):
    if len(sx) < 7 or sx[1] != 0x7D or sx[2] != 0x01:
        return False
    mid, idx, cnt = sx[3], sx[4], sx[5]
    parts = _bridge['parts'].setdefault(mid, {})
    parts[idx] = bytes(sx[6:-1]).decode('ascii')
    if len(parts) < cnt:
        return True
    code = ''.join(parts[i] for i in range(cnt))
    del _bridge['parts'][mid]
    lines = []

    def out(*a):
        lines.append(' '.join(str(x) for x in a))
    import patterns
    ns = dict(out=out, transport=transport, device=device, ui=ui, midi=midi, general=general,
              plugins=plugins, mixer=mixer, patterns=patterns, channels=channels, link=_link, clock=_clock, G=globals())
    try:
        exec(code, ns)
    except Exception as e:
        lines.append('ERROR %r' % (e,))
    data = '\n'.join(lines).encode('ascii', 'backslashreplace') or b'(no output)'
    chunks = [data[i:i + 200] for i in range(0, len(data), 200)]
    for i, c in enumerate(chunks):
        device.midiOutSysex(bytes([0xF0, 0x7D, 0x02, mid, i, len(chunks)]) + c + bytes([0xF7]))
    return True
