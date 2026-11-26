Domino English Translation 
Build 5-nightly.20261019 (1.45 dev009-en.5-nightly.20261019)

Thank you for using the Domino English Translation.

Domino is a MIDI editor that is used for creating MIDI songs/musics. Domino is used by various blackers in the Black MIDI ecosystem.

Since Domino is an abandonware, and it's original language is Japanese, many people tried to translate it using resource editing tools. Some of it are outdated, while others are incomplete.

This project is made to unify the translations made by community, while trying to complete it for easier usage.

You can download the latest version or even contribute by clicking the links below.

Repository      : https://github.com/Hans5958/Domino-English-Translation/
Releases        : https://github.com/Hans5958/Domino-English-Translation/releases
Domino site     : http://takabosoft.com/domino


Completed translation (local build, 2026-10-23)
-----------------------------------------------
Based on the build above, with the remaining Japanese translated:

- Domino.exe: all 544 hardcoded messages (undo names, warnings, error
  messages, preference page names, mouse actions, file dialog filters,
  window title "Untitled", ...) are written in English directly in the
  exe. No dominohook.dll is needed (and the old 32-bit dominohook.dll
  cannot load into this 64-bit Domino anyway).
  Messages that did not fit in the original space live in a new
  section named .entxt. The compiler had baked the Japanese text
  lengths into 224 places; those were updated to the English lengths.
- Two leftover dialog texts (bug report link, a full-width space).
- Corrections to the community's own English (2026-11-01): "Tranpose..."
  is now "Transpose..." (Event menu and right-click menus), and the
  Preferences > MIDI-OUT instruction was shortened so it fits on its
  line ("Click a box to select a device and its sound source ...").
  Also corrected Program Change "Macro:" to "Map:" and made all
  Selection Filter checkboxes say "Invert Selection".
- Module folder: every Japanese description, folder name and label in
  SC-88Pro, SC-8850, ok_GSm, ok_XG2k and ok_XGb is now English
  (1712 strings). Two module names changed their Japanese comma to an
  English one: "XG2k (MU2000EX, MU1000EX)" and "XGb (S-YXG50, MU50)".
  Labels that already show English keep their Japanese next to it,
  e.g. "255 Rest (休符)" and "Note No. (音階)".
- Manual folder: the community English manual from
  https://hans5958.id/Domino-English-Translation/en/ (downloaded
  2026-10-23), plus index.htm so F1 opens it. The page text is
  English; the screenshots were re-lettered into English, preserving
  Japanese that appears beside its English meaning. The originals,
  specs and tools are in
  C:\_main\domino\translation-tools\manual-shots.

Two Japanese strings are intentionally left inside Domino.exe because
they are data, not text you ever see: a full-width digit table used to
convert typed numbers, and a sample string used to measure font size.
