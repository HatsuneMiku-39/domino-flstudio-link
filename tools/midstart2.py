# Start FL at a bar through the bridge (FL leads) and log what Domino plays on loopMIDI "1".
#   python midstart2.py <bar> [seconds]
import sys, time, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fl import Bridge
import listen_lib

bar = int(sys.argv[1]); secs = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
lis = listen_lib.Listener('1')
br = Bridge()
try:
    print(br.run("general.processRECEvent(midi.REC_Tempo, 140000, midi.REC_UpdateValue | midi.REC_UpdateControl)\n"
                 "transport.setSongPos(%d, midi.SONGLENGTH_ABSTICKS)\n"
                 "out('FL before start', transport.getSongPosHint(), 'state', link.state)" % ((bar - 1) * 4 * 96)))
    time.sleep(0.3)
    t0 = time.perf_counter()
    print(br.run("transport.start()\nout('started')"))
    time.sleep(secs)
    print(br.run("out('FL at stop', transport.getSongPosHint(), 'state', link.state)\ntransport.stop()"))
    time.sleep(0.5)
finally:
    br.close()
    lis.close()
beat = 60000 / 140
for t, st, d1, d2 in lis.log:
    if st & 0xF0 == 0x90 and d2:
        print('%7.1f ms after FL start: note-on ch%d key %d' % ((t - t0) * 1000, (st & 15) + 1, d1))
