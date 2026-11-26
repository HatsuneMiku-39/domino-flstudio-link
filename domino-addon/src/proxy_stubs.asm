; version.dll pass-through: every export jumps to the same function of the real system version.dll.
; g_real is filled in DllMain (addon.cpp), in the order of the exports below.

EXTERN g_real:QWORD

.code

STUB MACRO name, index
name PROC
    jmp QWORD PTR [g_real + index * 8]
name ENDP
ENDM

STUB stub_GetFileVersionInfoA, 0
STUB stub_GetFileVersionInfoByHandle, 1
STUB stub_GetFileVersionInfoExA, 2
STUB stub_GetFileVersionInfoExW, 3
STUB stub_GetFileVersionInfoSizeA, 4
STUB stub_GetFileVersionInfoSizeExA, 5
STUB stub_GetFileVersionInfoSizeExW, 6
STUB stub_GetFileVersionInfoSizeW, 7
STUB stub_GetFileVersionInfoW, 8
STUB stub_VerFindFileA, 9
STUB stub_VerFindFileW, 10
STUB stub_VerInstallFileA, 11
STUB stub_VerInstallFileW, 12
STUB stub_VerQueryValueA, 13
STUB stub_VerQueryValueW, 14

END
