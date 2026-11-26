# Writes clock tick times (one per line) for the C++ tempo test (domino-addon\tests\tempo_test.cpp):
# the recorded Domino clock in data\ and the simulated cases of sim_tempo.py. Also prints what the Python
# tempo reader sends for each, to compare.
#   python export_ticks.py <output folder>
import sys, os, json, random, io, contextlib
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
with contextlib.redirect_stdout(io.StringIO()):
    import sim_tempo
from replay_tempo import helper

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
cases = {'recorded_40_jumps': json.load(open(os.path.join(here, 'data', 'clock_jumps_140.json')))['clocks']}
random.seed(7)
plans = {
    'steady_140': [('play', 140, 20)],
    'tempo_140_to_120': [('play', 140, 4), ('play', 120, 4)],
    'tempo_140_to_139_5': [('play', 140, 4), ('play', 139.5, 6)],
    'steady_97_5': [('play', 97.5, 10)],
    'stop_then_140': [('play', 97.5, 3), ('stop', 1), ('play', 140, 3)],
}
for name, plan in plans.items():
    cases[name] = sim_tempo.clock(plan)
for name, ticks in cases.items():
    with open(os.path.join(out, name + '.txt'), 'w') as f:
        f.write('\n'.join('%.9f' % t for t in ticks))
    r = helper.TempoReader()
    sends = [(round(t - ticks[0], 2), b) for t in ticks for b in [r.feed(t)] if b is not None]
    print('%-22s python: %s' % (name, sends))
