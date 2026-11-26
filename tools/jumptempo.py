# Domino leads (MMC play), FL's playhead is moved while playing; log FL's tempo and position over time.
#   python jumptempo.py <bar> [<start tempo in FL>]
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fl import Bridge
import listen_lib

bar = int(sys.argv[1]); start_tempo = float(sys.argv[2]) if len(sys.argv) > 2 else 97.5
lis = listen_lib.Listener('1')
br = Bridge()
STATE = "out('state', link.state, 'hint', transport.getSongPosHint(), 'tempo', mixer.getCurrentTempo())"
try:
    br.run("general.processRECEvent(midi.REC_Tempo, %d, midi.REC_UpdateValue | midi.REC_UpdateControl)\nout('ok')" % (start_tempo * 1000))
    br.run("import time\nG['T0'] = time.time()\nout('ok')")
    br.send([0xF0, 0x7F, 0x7F, 0x06, 0x44, 0x06, 0x01, 0x60, 0, 0, 0, 0, 0xF7])
    br.send([0xF0, 0x7F, 0x7F, 0x06, 0x02, 0xF7])
    t0 = time.perf_counter()
    for _ in range(5):
        time.sleep(0.25); print('before %.2f s' % (time.perf_counter() - t0), br.run(STATE))
    tj = time.perf_counter()
    print(br.run("transport.setSongPos(%d, midi.SONGLENGTH_ABSTICKS)\nout('JUMP moved to', transport.getSongPosHint())" % ((bar - 1) * 4 * 96)))
    for _ in range(12):
        time.sleep(0.25); print('after  %.2f s' % (time.perf_counter() - t0), br.run(STATE))
    br.send([0xF0, 0x7F, 0x7F, 0x06, 0x01, 0xF7])
    time.sleep(0.4)
finally:
    br.close()
    lis.close()
for t, st, d1, d2 in lis.log:
    if st & 0xF0 == 0x90 and d2 and t > tj:
        print('Domino note %+7.1f ms after the FL jump: ch%d key %d' % ((t - tj) * 1000, (st & 15) + 1, d1))
        break
