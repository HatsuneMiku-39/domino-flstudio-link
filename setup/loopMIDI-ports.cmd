@echo off
rem Adds the loopMIDI ports "1".."16" and "SysEx" for Domino Link.
rem loopMIDI keeps its port list in the registry and saves it when it exits, so it must be closed while this runs.
setlocal
set "FIND=%SystemRoot%\System32\find.exe"

tasklist /fi "imagename eq loopMIDI.exe" | "%FIND%" /i "loopMIDI.exe" >nul
if not errorlevel 1 (
  echo loopMIDI is running. Close it ^(tray icon, Exit^), then run this again.
  pause
  exit /b 1
)
for %%P in (1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 SysEx) do (
  reg add "HKCU\Software\Tobias Erichsen\loopMIDI\Ports" /v "%%P" /t REG_DWORD /d 1 /f >nul || goto failed
)
echo The loopMIDI ports "1" to "16" and "SysEx" are added. Start loopMIDI: they appear there.
pause
exit /b 0

:failed
echo Something went wrong: the ports couldn't be added.
pause
exit /b 1
