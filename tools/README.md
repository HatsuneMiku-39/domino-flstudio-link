# Test tools

Used to test Domino Link with FL Studio 21.0.3 and Domino 1.45. Not needed for normal use. Most need Python 3 and
loopMIDI; use a copy of Domino for tests, with `sync_test.mid` (140 BPM) open.

**Test bridge:** `make_test_build.py` writes `device_DominoLink_with_test_bridge.py`: the FL script plus a bridge
(`test_bridge_code.py`) that runs Python sent as SysEx on loopMIDI `SysEx` inside FL and sends the output back, and
a log of every playhead move the script makes (`link.log`). `fl.py` is the other end:

    python fl.py "out(transport.getSongPosHint(), mixer.getCurrentTempo())"

Install it in place of `device_DominoLink.py` only for testing, restart FL, and put the normal script back
afterwards: while it's installed, any program can run code inside FL through that port.

| Tool | What it does | Needs the bridge |
|---|---|---|
| `addon_test.py <Domino pid>` | Domino add-on: pre-roll on Domino's Play/Stop, the playhead coming back, the tempo it sends | no |
| `full_chain_test.py alone\|chain [pid]` | FL alone (Play mustn't move FL's playhead); FL leading Domino; Domino leading FL with pre-roll and tempo | yes |
| `export_ticks.py <dir>` | clock tick files for the add-on's C++ tempo test, and what the Python reader sends for them | no |
| `jumptempo.py <bar> [tempo]` | Domino plays, FL's playhead jumps to a bar; logs FL's tempo and position | yes |
| `midstart2.py <bar>` | starts FL at a bar; logs where Domino starts | yes |
| `offset_test.py <project.flp>` | records the test song into FL (snap off) and prints how far the notes land from the beat: measures `START_OFFSET_MS` | yes |
| `space_test.py` | presses Space in FL; logs the MMC the script sends and Domino's notes | no |
| `replay_tempo.py data\clock_jumps_140.json` | replays a recording of Domino's clock (40 jumps) through the old and current Python tempo reader | no |
| `sim_tempo.py` | simulated clocks: tempo changes, stops, jumps, 40–300 BPM | no |
| `mmc.py play [ms]` / `mmc.py stop` | starts/stops Domino like another program would | no |
| `mid.py` | sends test notes and controllers into the loopMIDI ports | no |
| `restart_fl.py <project.flp>` | closes FL (save first) and opens a project | no |
| `filedlg.py <path>` | fills FL's open/save dialog | no |
| `latency_test.py vaio\|cable` | time from a MIDI note to its sound in Voicemeeter, for comparing FL's audio paths | no |
| `held_note_test.py none\|start\|jump` | does FL cut a held note when it starts or jumps? (Voicemeeter meter) | no |
| `armed_start_test.py [ms] [armed]` | Domino start with FL's record armed: logs what the script sends back | no |
| `mmc_stress.py <Domino.exe> <song>` | how many MMC commands Domino takes in a row (optionally with other SysEx mixed in) | no |
| `mmc_after_commands.py <pid>` | does Domino still take MMC after menu commands sent to its window? | no |
| `preroll_test.py` | the old Python helper's pre-roll, without the keyboard | no |

`python-helper\domino_link_helper.pyw` is the earlier Python helper (tempo and a Space-key pre-roll), replaced by
the add-on. It stays here as the reference for the tempo algorithm (`replay_tempo.py`, `sim_tempo.py`). Don't run it
together with the add-on: both would step the playhead back.

`listen_lib.py` logs a loopMIDI port.
