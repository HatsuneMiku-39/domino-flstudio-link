# Developer notes

## Parts

| Part | Where | Language |
|---|---|---|
| FL Studio script | `setup\fl-studio-script\Domino Link\device_DominoLink.py` | Python (FL Studio's MIDI scripting) |
| Domino add-on | `domino-addon\src\` → `domino-addon\dist\version.dll` | C++ / x64 assembly |
| FL templates and their generator | `setup\fl-studio-templates\`, `tools\template-maker\` | FLP files, Python |
| Test tools | `tools\` | Python |
| English Domino 1.45 with the add-on | `domino\` (copied in by `tools\update_domino.cmd`; stored byte-for-byte, see `.gitattributes`) | — |

## The ports

- loopMIDI `1`–`16`: Domino's MIDI-OUT ports A–P. Notes and controllers for
  FL's instruments; FL inputs 1–16 run the script as `PortRouter`.
- loopMIDI `SysEx`: FL input/output port 17, the script as `Link`.
  - Domino → FL: MIDI Time Code (Domino's MTC master) and the tempo
    (`F0 7D 10 b1 b2 b3 F7`, bpm × 100 in 3 × 7 bits) from the add-on.
  - FL → Domino: MMC locate/play/stop (Domino's MMC slave, device ID 127).

## The FL script

- `Link` follows Domino's timecode (`FOLLOW`) or leads Domino with MMC
  (`LEAD`). Positions go through ticks and the current tempo:
  `transport.getSongPos(SONGLENGTH_MS)` ignores tempo changes made by scripts.
- `START_OFFSET_MS` keeps FL ahead of Domino by FL's own recording latency
  compensation, so recorded notes land on the beat.
- When FL leads, FL's playhead is only moved once Domino's timecode arrives
  (`align_pending`). Without Domino, the script never moves FL's playhead.
- MMC locate uses whole frames: Domino ignores sub-frames.
- FL scripts can't open files and have no `re`; FL 21.0.3 doesn't pass MIDI clock
  to scripts; *Update MIDI scripts* doesn't reload changed code (restart FL).
- `PortRouter` forwards controllers to the VST wrapper's *MIDI CC #n* parameters
  (4096 + n) and channel aftertouch (4224) with `processRECEvent`, and pitch bend
  to the channel's pitch (scaled by the channel's pitch range). It finds the FL
  channel by the mixer track name (`A01`, `B10 drums`, …).

## The Domino add-on (`version.dll`)

Domino 1.45 x64 imports `VERSION.dll`, which isn't a KnownDLL, so Windows loads
a `version.dll` from Domino's folder first. `proxy_stubs.asm` passes all 15 of
its own functions on to the system's version.dll (`g_real`, filled in
`DllMain`); `VerLanguageNameA/W` are forwarded to KERNEL32 like in the original.

Inside Domino (`addon.cpp`):

- **Hooks in Domino's import table** (set in `DllMain`; the table is filled by
  then):
  - `USER32!GetMessageA`/`PeekMessageA`: the first call on Domino's main thread
    starts the UI part (`UiStart`).
  - `WINMM!midiOutShortMsg`: timestamps (QueryPerformanceCounter) of the clock
    ticks (`F8`) Domino sends on its first clock port feed `TempoReader`
    (`tempo.h`, the same algorithm as `tools\python-helper`).
  - `WINMM!midiOutOpen`/`midiOutClose`: remembers Domino's own handle on its
    MTC port, because a MIDI port can't be opened twice in one program; the
    tempo goes out through that handle. Its name comes from Domino's
    `MidiSync.ini` (`[MTCMaster] MidiDeviceName`).
- **Pre-roll:** Domino is an MFC program. Its Play/Stop command (ID 32886) is
  handled through a message map entry `{WM_COMMAND, 0, 32886, 32886, sig, pfn}`
  in `.rdata`; the add-on replaces `pfn` with `PlayStopHook`, which moves the
  playhead back and then calls Domino's handler. A timer watches for the stop
  and puts the playhead back if Domino left it at the pre-roll start.
- **Finding Domino's internals** (by code pattern, so other builds of the same
  version work and anything else is refused):

| What | Found in | 1.45 x64 |
|---|---|---|
| "playing" flag (byte) | Play/Stop handler: `cmp byte [rcx+X],0` | `+0x148` |
| playhead (int, ticks) | Previous Quantize Unit (33326): `mov edx,[r9+X]` | `+0x108` |
| song object pointer | Previous Quantize Unit: `mov rcx,[rcx+X]` | `+0xF0` |
| ticks per quarter note | quantize-to-ticks routine: `imul eax,[rcx+X]` | song `+0x18` |
| SetPlayhead(this, tick, 1, -, 0) | Start of the Song (32894): `xor edx,edx / call` | RVA `0xD3020` |

- **Preferences:** a `WH_CALLWNDPROCRET` hook on Domino's main thread spots the
  Synchronization page by its controls (1420, 1423, 1466) on `WM_INITDIALOG` and
  adds the "FL Studio link" controls below "Broadcast timing clock" (the page has
  room from y = 130 dialog units). A `WH_CALLWNDPROC` hook sees OK/Cancel on the
  Preferences window; OK saves `DominoLink.ini` (in `IniFiles\<user>\`).
- **First start:** Domino keeps its settings in `IniFiles\<user>\` and creates
  it empty for a new user. If it doesn't exist when the add-on loads, a timer
  waits for the main window and asks whether to load
  `..\setup\domino-settings\DominoLink.dmc`. Yes does what File → Import
  Preferences does: start Domino with `/config"<file>" /wp<pid>` and send
  `WM_CLOSE` to the main window; the new Domino waits for the old one, deletes
  `IniFiles\<user>\` and unpacks the file there. Never asked when the command
  line has `/config`.
- Log: `%TEMP%\DominoLink.log`.

Tools used to find all this: `capstone` for disassembly and the MFC message map
search; the dialog layout comes from Domino's DIALOG resources.

## Building

`domino-addon\build.cmd` (needs Visual Studio with the C++ tools; finds them with
vswhere). Static runtime (`/MT`), so the DLL needs nothing else installed.
Output: `domino-addon\dist\version.dll` and `build\tempo_test.exe`.

## Testing

See `tools\README.md`. The important ones:

- `tools\export_ticks.py <dir>` + `build\tempo_test.exe <dir>\<case>.txt`: the C++
  tempo reader against the Python one (recorded Domino clock with 40 jumps, and
  simulated tempo changes); they must print the same.
- `tools\addon_test.py <Domino pid>`: pre-roll, playhead restore and tempo in a
  running Domino with `tools\sync_test.mid`.
- `tools\make_test_build.py`: the FL script plus a test bridge, for
  `full_chain_test.py`, `jumptempo.py`, `offset_test.py` and others. Never leave
  the test build installed.

Use a copy of Domino for tests (with its own `IniFiles`), not the one you
compose with.
