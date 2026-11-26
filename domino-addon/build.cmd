@echo off
rem Builds the Domino Link add-on (version.dll, 64-bit) with Visual Studio's C++ tools.
rem Result: dist\version.dll  - copy it next to Domino.exe.
setlocal
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
set "VS="
for /f "usebackq delims=" %%i in (`^""%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath^"`) do set "VS=%%i"
if not defined VS (
  echo Visual Studio with the C++ tools was not found.
  exit /b 1
)
call "%VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0"
if not exist build mkdir build
if not exist dist mkdir dist
ml64 /nologo /c /Fo build\proxy_stubs.obj src\proxy_stubs.asm || exit /b 1
cl /nologo /O2 /MT /EHsc /W3 /std:c++17 /LD /Fo:build\ /Fe:build\version.dll src\addon.cpp build\proxy_stubs.obj ^
   /link /DEF:src\version.def user32.lib winmm.lib || exit /b 1
copy /y build\version.dll dist\version.dll >nul || exit /b 1
cl /nologo /O2 /MT /EHsc /W3 /std:c++17 /Fo:build\ /Fe:build\tempo_test.exe tests\tempo_test.cpp || exit /b 1
echo Built dist\version.dll
