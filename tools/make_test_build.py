# Makes the test build of the FL script: the normal script, plus the test bridge (test_bridge_code.py) that runs
# Python sent as SysEx on loopMIDI "SysEx" inside FL, plus a log of every playhead move (link.log).
# Install it in place of device_DominoLink.py only for testing: while it's installed, any program can run code
# inside FL through that port.
#   python make_test_build.py [output file]
import os, sys
here = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(here, '..', 'setup', 'fl-studio-script', 'Domino Link', 'device_DominoLink.py')
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, 'device_DominoLink_with_test_bridge.py')
s = open(src, encoding='utf-8').read()


def insert_after(text, anchor, addition):
    assert text.count(anchor) == 1, anchor
    return text.replace(anchor, anchor + addition)


s = insert_after(s, "        sysex = event.sysex or b''\n",
                 "        if _bridge_sysex(sysex):\n            event.handled = True\n            return\n")
s = insert_after(s, "    def set_fl_pos(self, ms):\n",
                 "        import sys\n        f = sys._getframe(1)\n"
                 "        self.log = (getattr(self, 'log', []) + [('set_fl_pos', round(ms), f.f_code.co_name, f.f_lineno,"
                 " round(self.clock(), 3))])[-30:]\n")
bridge = open(os.path.join(here, 'test_bridge_code.py'), encoding='utf-8').read().split('\n', 1)[1]
open(out, 'w', encoding='utf-8', newline='').write(s.rstrip('\n') + '\n\n\n' + bridge)
print('wrote', out)
