@echo off
rem Sets up FL Studio (21 or newer) for Domino Link:
rem   1. copies the Domino Link script and the templates into FL's user data folder
rem   2. makes FL's MIDI settings: inputs "1".."16" on ports 1-16 and "SysEx" on port 17, all with the
rem      Domino Link script; output "SysEx" on port 17
rem FL saves its own settings when it closes, so it must be closed while this runs.
rem   fl-studio-setup.cmd [FL user data folder]   (default: Documents\Image-Line\FL Studio)
setlocal
set "FIND=%SystemRoot%\System32\find.exe"
set "IL=HKCU\Software\Image-Line"
set "SRC=%~dp0"
set "FLDATA=%~1"

for %%E in (FL64.exe FL.exe) do (
  tasklist /fi "imagename eq %%E" | "%FIND%" /i "%%E" >nul && (echo FL Studio is running. Close it, then run this again. & pause & exit /b 1)
)

echo 1. Script and templates
if "%FLDATA%"=="" for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('MyDocuments')"`) do set "FLDATA=%%D\Image-Line\FL Studio"
xcopy /y /i /q "%SRC%fl-studio-script\Domino Link" "%FLDATA%\Settings\Hardware\Domino Link" >nul || goto failed
xcopy /y /i /q /s "%SRC%fl-studio-templates" "%FLDATA%\Projects\Templates\Domino" >nul || goto failed
echo    %FLDATA%\Settings\Hardware\Domino Link
echo    %FLDATA%\Projects\Templates\Domino

echo 2. MIDI settings
set FOUND=
for /f "delims=" %%K in ('reg query "%IL%" 2^>nul ^| findstr /r /c:"\\FL Studio [0-9][0-9]*$"') do (
  for /f "tokens=3" %%V in ("%%~nxK") do if %%V geq 21 (
    set FOUND=1
    call :flmidi "%%K" || goto failed
  )
)
if not defined FOUND (
  echo    No settings of FL Studio 21 or newer found: start FL Studio once, close it, and run this again.
  pause
  exit /b 1
)
echo Done. In FL Studio: File, New from template, Domino.
pause
exit /b 0

:flmidi
set "K=%~1\Devices"
for /l %%N in (1,1,16) do (
  reg add "%K%\MIDI input\%%N" /v Type /t REG_SZ /d "-3" /f >nul || exit /b 1
  reg add "%K%\MIDI input\%%N" /v ScriptFolder /t REG_SZ /d "Domino Link" /f >nul || exit /b 1
  reg add "%K%\MIDI input\%%N" /v Port /t REG_SZ /d "%%N" /f >nul || exit /b 1
  reg add "%K%\MIDI input\%%N" /v Enabled /t REG_SZ /d "1" /f >nul || exit /b 1
)
reg add "%K%\MIDI input\SysEx" /v Type /t REG_SZ /d "-3" /f >nul || exit /b 1
reg add "%K%\MIDI input\SysEx" /v ScriptFolder /t REG_SZ /d "Domino Link" /f >nul || exit /b 1
reg add "%K%\MIDI input\SysEx" /v Port /t REG_SZ /d "17" /f >nul || exit /b 1
reg add "%K%\MIDI input\SysEx" /v Enabled /t REG_SZ /d "1" /f >nul || exit /b 1
reg add "%K%\MIDI output\SysEx" /v Port /t REG_SZ /d "17" /f >nul || exit /b 1
reg add "%K%\MIDI output\SysEx" /v Sync /t REG_SZ /d "0" /f >nul || exit /b 1
echo    %~nx1
exit /b 0

:failed
echo Something went wrong: the settings couldn't be made.
pause
exit /b 1
