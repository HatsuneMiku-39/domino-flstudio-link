@echo off
rem Copies the English Domino into domino\ (without the personal settings in IniFiles) and puts the current
rem add-on next to it. Run it after rebuilding Domino.exe or the add-on, then commit.
rem   update_domino.cmd [folder of the English Domino]   (default C:\_main\domino\1.45-english)
setlocal
set "SRC=%~1"
if "%SRC%"=="" set "SRC=C:\_main\domino\1.45-english"
set "DST=%~dp0..\domino"
if not exist "%SRC%\Domino.exe" (
  echo No Domino.exe in "%SRC%".
  exit /b 1
)
robocopy "%SRC%" "%DST%" /MIR /XD "%SRC%\IniFiles" "%DST%\IniFiles" /NFL /NDL /NJH /NJS /NP
if errorlevel 8 exit /b 1
if not exist "%DST%\IniFiles" mkdir "%DST%\IniFiles"
copy /y "%~dp0..\domino-addon\dist\version.dll" "%DST%\version.dll" >nul || exit /b 1
echo Domino copied to %DST%
exit /b 0
