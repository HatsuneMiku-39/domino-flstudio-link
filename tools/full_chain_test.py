# Whole chain with the FL test build (make_test_build.py) and Domino with the add-on:
#   A) FL alone (Domino closed): Play in FL must not move FL's playhead
#   B) FL leads: Domino follows; FL is lined up only when Domino answers
#   C) Domino leads with its Play/Stop (pre-roll): FL follows and takes over Domino's tempo from the add-on
#   python full_chain_test.py alone|chain [Domino pid]
import sys, os, time, ctypes, ctypes.wintypes as wt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fl import Bridge
import listen_lib

mode = sys.argv[1]
br = Bridge()
STATE = "out('state', link.state, 'playing', transport.isPlaying(), 'pos', transport.getSongPosHint(), 'tempo', mixer.getCurrentTempo())"
moves = "out([x for x in getattr(link, 'log', []) if x[0] == 'set_fl_pos'][-5:])"
try:
    br.run("link.log = []\ntransport.stop()\nout('ok')")
    time.sleep(0.5)
    if mode == 'alone':
        print('A) FL alone')
        print('  ', br.run("transport.setSongPos(0, midi.SONGLENGTH_ABSTICKS)\nout('before', transport.getSongPos(midi.SONGLENGTH_ABSTICKS), 'ticks')"))
        br.run("transport.start()\nout('ok')")
        time.sleep(0.6)
        print('  ', br.run(STATE))
        print('   playhead moves by the script:', br.run(moves))
        br.run("transport.stop()\nout('ok')")
    else:
        pid = int(sys.argv[2])
        u = ctypes.WinDLL('user32')
        WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        mains = []
        def cb(h, l):
            q = wt.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(q))
            b = ctypes.create_unicode_buffer(256); u.GetWindowTextW(h, b, 256)
            if q.value == pid and u.IsWindowVisible(h) and b.value.endswith(' - Domino'): mains.append(h)
            return True
        u.EnumWindows(WNDENUMPROC(cb), 0)
        domino = mains[0]
        print('B) FL leads from bar 2')
        lis = listen_lib.Listener('1')
        br.run("general.processRECEvent(midi.REC_Tempo, 140000, midi.REC_UpdateValue | midi.REC_UpdateControl)\n"
               "transport.setSongPos(%d, midi.SONGLENGTH_ABSTICKS)\nout('ok')" % (4 * 96))
        time.sleep(0.3)
        t0 = time.perf_counter()
        br.run("transport.start()\nout('ok')")
        time.sleep(1.2)
        print('  ', br.run(STATE))
        print('   playhead moves by the script:', br.run(moves))
        br.run("transport.stop()\nout('ok')")
        time.sleep(0.6)
        lis.close()
        notes = [(t - t0) * 1000 for t, st, a, b in lis.log if st & 0xF0 == 0x90 and b]
        print('   Domino first note %.0f ms after FL started' % notes[0] if notes else '   Domino played nothing')
        print("C) Domino's Play/Stop (pre-roll), FL at 120 BPM before")
        br.run("link.log = []\ngeneral.processRECEvent(midi.REC_Tempo, 120000, midi.REC_UpdateValue | midi.REC_UpdateControl)\nout('ok')")
        br.send([0xF0, 0x7F, 0x7F, 0x06, 0x44, 0x06, 0x01, 0x60, 0, 1, 21, 0, 0xF7])   # Domino's cursor to 1.7 s
        time.sleep(0.4)
        u.PostMessageW(domino, 0x0111, 32886, 0)
        time.sleep(1.5)
        print('  ', br.run(STATE))
        print('   playhead moves by the script:', br.run(moves))
        u.PostMessageW(domino, 0x0111, 32886, 0)
        time.sleep(0.8)
        print('   after stop:', br.run(STATE))
finally:
    br.close()
