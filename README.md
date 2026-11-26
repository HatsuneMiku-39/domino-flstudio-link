# Domino FLStudio Link

Write your music in **Domino** and hear it with your **FL Studio** instruments
(VSTs), as if Domino were a part of FL:

- **FL follows Domino:** Play, Stop, jumps, and the tempo.
- **Domino follows FL:** Play and Stop in FL, and clicks in FL's timeline while
  playing.
- **Each Domino track plays its own FL instrument:** 16 per Domino port; the
  ready-made templates have 16 (port A) or 32 (ports A and B).
- **Modulation reaches the instruments:** mod wheel, pitch bend, expression,
  volume and every other controller.
- **FL can record** everything Domino plays.
- **Pre-roll:** Play in Domino starts a little before the playhead, so the
  first note is never cut off. You set how far in Domino's Preferences.

You only use FL to put instruments on channels; everything else happens in
Domino. You start Domino as always (`Domino.exe`); FL Studio without Domino
works exactly as before.

## What's in here

| Folder | What it is |
|---|---|
| `domino\` | Domino 1.45 in English (64-bit), with the add-on already in place. Run `domino\Domino.exe`. |
| `SETUP.txt` | The setup steps in short. |
| `setup\` | `loopMIDI-ports.cmd` (creates the loopMIDI ports), `fl-studio-setup.cmd` (copies the FL script and templates, makes FL's MIDI settings), `domino-settings\DominoLink.dmc` (Domino's settings, for File → Import Preferences; also to get them back), `fl-studio-script\Domino Link\` (the FL Studio MIDI script that does the syncing), `fl-studio-templates\` (two FL project templates with everything prepared). |
| `domino-addon\` | Source code of the add-on (`version.dll`) and its build script. Only for developers. |
| `tools\`, `docs\` | Test tools, the template generator (`tools\template-maker`) and developer notes. Only for developers. |

## What you need

- **Windows** 10 or 11.
- **Domino:** the English Domino 1.45 is included in `domino\`. The add-on also
  works with another 64-bit Domino 1.45 (the original Japanese version has the
  same settings in the same places).
- **FL Studio 21** or newer. Tested with 21.0.3.
- **loopMIDI** (free) by Tobias Erichsen:
  <https://www.tobias-erichsen.de/software/loopmidi.html>
- A low-latency audio driver for FL (ASIO) is recommended, so you hear Domino's
  notes without much delay.

## Setup (once)

### Quick setup

Follow `SETUP.txt`: two double-clicks in `setup\` (`loopMIDI-ports.cmd`,
`fl-studio-setup.cmd`) and importing `setup\domino-settings\DominoLink.dmc` in
Domino.

The sections below describe the same steps by hand, in case you want to check
or change something.

### 1. loopMIDI

Create these ports in loopMIDI; the names must match exactly:

- `1`, `2`, … one for each Domino port you use, up to `16` (port A = `1`,
  port B = `2`, …). At least `1`.
- `SysEx`. It carries the sync messages between the two programs.

Let loopMIDI start with Windows (its tray icon menu), so the ports are always
there.

### 2. Domino and the add-on

- **With the included English Domino:** nothing to do. Copy the `domino` folder
  wherever you like and run `Domino.exe` from it; the add-on (`version.dll`) is
  already next to it.
- **With your own Domino 1.45 x64:** close Domino, then copy
  `domino\version.dll` into the folder where your `Domino.exe` is.

Domino loads the add-on by itself every time it starts. To remove it, delete
`version.dll` from Domino's folder.

### 3. Domino's settings

**The quick way:** the first time Domino starts for your Windows user, the
add-on asks whether to load the Domino Link settings. Yes makes Domino restart
with all the settings below already made.

To get them back later (or with your own Domino): **File → Import
Preferences** and pick `setup\domino-settings\DominoLink.dmc`. Importing
replaces *all* of Domino's preferences (window layout, key bindings, …); if
you've already set up your Domino the way you like it, save yours first with
File → Export Preferences, or make the settings by hand.

**By hand:** start Domino and open the Preferences:

- **MIDI-OUT:** port A → `1`, port B → `2`, and so on for the ports you use.
- **Synchronization:**
  - **Enable MTC Master** ✔, MIDI-OUT device `SysEx`, Frame Rate **30**.
  - **Enable MMC Slave** ✔, MIDI-IN device `SysEx`, Device ID **127**.
  - **Broadcast timing clock (MIDI clock)** ✔.
  - **FL Studio link** (the add-on's own section, at the bottom):
    - **Pre-roll on Play:** how far before the playhead Play starts, in 16th
      notes or beats. 0 turns it off.
    - **Send the tempo to FL Studio** ✔.
- **MIDI-IN:** don't pick the loopMIDI ports `1`–`16` as inputs. That would
  make a loop.

If the "FL Studio link" section is missing, the add-on isn't loaded: check that
`version.dll` is in the same folder as `Domino.exe`.

### 4. The FL Studio script

`setup\fl-studio-setup.cmd` does this and the next two steps. By hand: copy the
folder `setup\fl-studio-script\Domino Link` into

`Documents\Image-Line\FL Studio\Settings\Hardware\`

so that the file ends up at
`...\Settings\Hardware\Domino Link\device_DominoLink.py`. Then start (or
restart) FL Studio; FL only looks for new scripts when it starts.

### 5. FL Studio's MIDI settings

`setup\fl-studio-setup.cmd` makes these settings for FL Studio 21 and newer
(close FL first: it saves its own settings when it closes). To check or change
them: FL Studio → Options → MIDI settings:

- **Output** list, select `SysEx`: **Port 17**. *Send master sync* **off**.
- **Input** list, select `SysEx`: **Enable** ✔, Controller type
  **Domino Link (user)**, **Port 17**.
- **Input** list, each of `1` … `16`: **Enable** ✔, Controller type
  **Domino Link (user)**, **Port** = the same number (1–16).
- Your own MIDI keyboard: give it a port number that `1`–`17` don't use (for
  example 20). Otherwise it also plays the Domino instruments.

When it works, FL's hint bar shows **"Domino Link: ready (listening on port 17)"**.

### 6. The templates

Copy the two folders in `setup\fl-studio-templates` into

`Documents\Image-Line\FL Studio\Projects\Templates\Domino\`

(make the `Domino` folder). From now on, start a song in FL with File → New
from template → Domino → **Domino A1-A16** or **Domino A1-B16**.

## Using it

1. Start Domino.
2. In FL: File → New from template → Domino → **Domino A1-A16**.
3. Drag an instrument from FL's browser onto the channel button of each track
   you use. `A01` plays Domino port A, MIDI channel 1; `A02` channel 2, and so
   on. `A10 drums` is channel 10.
4. Write your song in Domino. You hear it through FL right away, even while FL
   is stopped.

| You do | What happens |
|---|---|
| Play (Space) in Domino | Domino starts the pre-roll distance before the playhead; FL plays along. After Stop, the playhead is back where you put it. |
| Stop in Domino | FL stops. |
| Click elsewhere in Domino while playing | FL jumps along. |
| Play / Stop in FL | Domino starts from FL's position (without pre-roll), and stops. |
| Click elsewhere in FL's timeline while playing | Domino jumps there. |

- **Tempo:** FL takes over Domino's tempo about half a second after Domino
  starts. Whole BPM values arrive exactly, others to 0.1 BPM.
- **Pre-roll:** works for Domino's Play/Stop command, so Space, the toolbar
  button and the menu all use it. At the very start of a song there's nothing
  before, so playback starts at the start.
- **Controllers:** mod wheel, pitch bend, expression, volume, pan and all other
  controllers go to the instrument on the matching mixer track (`A01`, …).
  Bank select, RPN/NRPN and program changes are left out, so Domino's setup bar
  doesn't reset the instruments. The sustain pedal is handled by FL itself.
- **Pitch bend range:** set the FL channel's pitch range (channel settings →
  *Pitch*, default ±2 semitones), the instrument's range and your song's range
  to the same value.
- **Recording into FL:** arm FL's record button, then press Play in Domino
  (or in FL). All instruments record at once into the selected pattern;
  Patterns menu → *Split by channel* gives each its own pattern.
- **FL without Domino:** works exactly as before. The script only moves FL's
  playhead once Domino answers.

### The templates

- `A01` … `A16` (and `B01` … `B16`): each channel only takes notes from its own
  Domino port and MIDI channel ("Receive notes from"), and has its own mixer
  track with the same name. The script uses the mixer track's name to find
  where the controllers go, so keep the names.
- `catcher - keep selected`: an empty, silent channel. FL sends notes that no
  channel takes (from an unused port, or your keyboard) to the *selected*
  channel; keep the catcher selected so they don't land on an instrument.
- `end of song (keep)`: a tiny silent clip at bar 500. Without anything in the
  playlist, FL's song position can't be read or set. Leave it there.
- The templates start in Song mode, which the sync needs.

More ports: in `tools\template-maker`, run
`python make_template.py CD "Domino C1-D16.flp"` for any one or two ports
(letters A–P; needs Python). Open the result in FL once, switch to Song mode,
save it into the Templates folder as `Domino\<name>\<name>.flp`.

## Recording timing (do this once)

FL shifts every note it records earlier by its own audio output delay. It
assumes you played along to sound that reached you late. Notes from Domino
aren't late, so the script keeps FL a little ahead of Domino to make up for it:
`START_OFFSET_MS` at the top of `device_DominoLink.py`. The right value depends
on your audio driver and buffer size (typical: 40–80).

To check it:

1. In Domino, write a bar of quarter notes for `A01`.
2. In FL, set the main snap (toolbar) to **(none)**. Otherwise FL snaps
   recorded notes to the grid and hides the error.
3. Arm recording in FL, press Play in Domino.
4. In FL's piano roll, zoom in: notes **early** → raise `START_OFFSET_MS`;
   notes **late** → lower it. At 120 BPM a 16th note is 125 ms.
5. Change the value in `Documents\Image-Line\FL Studio\Settings\Hardware\Domino Link\device_DominoLink.py`
   and restart FL.

Expect the notes to scatter by about one audio buffer from one start to the
next; aim for the middle.

## Settings

**Domino** (Preferences → Synchronization → FL Studio link): pre-roll length
and unit, and whether the tempo is sent to FL. They are saved in
`DominoLink.ini` next to Domino's own settings.

**FL script** (top of `device_DominoLink.py`, restart FL after changes):

- `START_OFFSET_MS`: see *Recording timing*.
- `STOP_TIMEOUT_MS` (200): Domino counts as stopped after this much silence.
- `JUMP_THRESHOLD_MS` (120) and `FL_JUMP_THRESHOLD_MS` (250): how big a
  position change counts as a jump in Domino / in FL.
- `CONTROL_DOMINO`, `FOLLOW_FL_JUMPS`: FL's Play/Stop and timeline clicks move
  Domino too.
- `FOLLOW_TEMPO`: take over the tempo from the add-on.
- `FORWARD_CONTROLLERS`, `PASS_CC`, `DROP_CC`: controller forwarding.
- `FORCE_SONG_MODE`, `DISABLE_COUNTDOWN`, `ALIGN_TO_DOMINO`: details of starting
  FL.

## Troubleshooting

- **No "FL Studio link" section in Domino's Preferences:** `version.dll` isn't
  next to `Domino.exe`, or it's not the 64-bit Domino 1.45. The add-on writes a
  log to `%TEMP%\DominoLink.log`.
- **The section says pre-roll isn't available:** this Domino build is different
  from the one the add-on knows; tempo sync still works.
- **No "ready" hint in FL:** check the Controller type of the `SysEx` input,
  and that the script file is in the right folder. FL → View → Script output
  shows script errors.
- **FL starts and stops by itself:** *Send master sync* is on for the `SysEx`
  output.
- **FL doesn't follow Domino:** Domino → Preferences → Synchronization →
  *Enable MTC Master* must be on, with `SysEx`.
- **Domino doesn't follow FL:** *Enable MMC Slave* must be on, with `SysEx`.
- **FL's tempo doesn't change:** check *Broadcast timing clock* and *Send the
  tempo to FL Studio* in Domino.
- **FL suddenly can't start Domino any more, or the tempo stops following:**
  close Domino and open it again. In testing this happened once, after a
  program on the `SysEx` port crashed. If it keeps happening, restart loopMIDI.
- **Domino doesn't start where FL is:** FL must be in Song mode, and the song
  needs something in the playlist (the templates' `end of song (keep)` clip).
- **A track is silent / the wrong instrument plays:** check the FL channel's
  *Receive notes from*.
- **Mod wheel or pitch bend doesn't reach an instrument:** its mixer track (or
  channel) must be named after the Domino port and channel, like `A01` or
  `B10 drums`.
- **Your keyboard plays the Domino instruments too:** give it a port number
  outside 1–17 in FL's MIDI settings.
- **A note doesn't sound when you start in its middle:** Domino only sends a
  note when its start is reached. The pre-roll helps when the note starts
  within the pre-roll distance before the playhead.

## Limits

- **Tempo changes inside a song:** FL follows them while playing, but doesn't
  record them, and positions are passed as time, which only matches the bars
  while the tempo stays the same. For a final version of such a song in FL,
  export a MIDI file from Domino and import it into FL.
- **Recording:** FL records the notes. Whether it also records the forwarded
  controllers as automation is untested; the MIDI file route copies
  everything.
- **Velocities:** FL bends incoming velocities with the *Note on velocity
  mapping* curve in its MIDI settings. Set it to a straight line if Domino's
  velocities must stay exact.
- **FL Studio 21.0:** after changing the script, restart FL (*Update MIDI
  scripts* didn't reload changed code in the tests).

## The included Domino

`domino\` is Domino 1.45 (© Takabo Soft) with the English translation (see
`domino\readme-translation.txt`) and the add-on. Personal settings aren't in the
repository: Domino keeps them in `domino\IniFiles\<your Windows user name>\`,
created on the first start. After rebuilding Domino.exe or the add-on,
`tools\update_domino.cmd` copies the current version in.

## How it works

See `docs\DEVELOPMENT.md` for the details. In short:

- Domino sends MIDI Time Code while it plays, but never Start/Stop/Song
  Position, so FL can't follow it by itself. The FL script reads Domino's
  timecode on the `SysEx` port and drives FL's transport itself. In the other
  direction, it sends Domino MMC commands (locate, play, stop).
- The Domino add-on is loaded by Domino as `version.dll` (it passes Windows'
  own version.dll functions on). It adds the pre-roll to Domino's Play/Stop
  command, turns Domino's MIDI clock into a tempo for the FL script (FL 21.0
  doesn't give scripts the clock), and adds its settings to the Preferences.
- Notes go straight to FL's channels through their *Receive notes from* locks.
  The script on the ports `1`–`16` sends controllers to the instruments as
  their *MIDI CC* parameters.
