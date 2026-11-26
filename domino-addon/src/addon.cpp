// Domino Link add-on for Domino 1.45 (x64).
//
// Put this DLL next to Domino.exe as "version.dll". Windows then loads it into Domino in place of the
// system version.dll, whose functions it passes on unchanged (proxy_stubs.asm). Inside Domino it adds:
//   * Pre-roll: Domino's Play/Stop command (Space, toolbar, menu) starts playback a set distance before
//     the playhead, so FL Studio is already running when the first note comes. When playback stops and
//     Domino puts the playhead back where playback started, it goes back to where you had put it.
//   * Tempo for FL Studio: the MIDI clock Domino sends ("Broadcast timing clock") is turned into a tempo
//     and sent to the Domino Link FL script as SysEx (F0 7D 10 bpm*100 in 3 x 7 bit F7) on the port
//     Domino sends its MIDI Time Code to.
//   * Settings for both on the Sync page of Domino's Preferences, saved in DominoLink.ini next to
//     Domino's own settings.
//   * On Domino's first start for a Windows user, it offers to load the Domino Link settings from
//     ..\setup\domino-settings\DominoLink.dmc, the way File > Import Preferences does.
// Domino's internals are found by the code of its own commands; if they don't match (another Domino
// build), the pre-roll stays off and the rest keeps working. A log is written to %TEMP%\DominoLink.log.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmsystem.h>
#include <commctrl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vector>
#include "tempo.h"

#define ADDON_VERSION "1.0.0"

// ------------------------------------------------------------------ version.dll pass-through --
extern "C" void* g_real[15] = {};
static const char* const kRealNames[15] = {
    "GetFileVersionInfoA", "GetFileVersionInfoByHandle", "GetFileVersionInfoExA", "GetFileVersionInfoExW",
    "GetFileVersionInfoSizeA", "GetFileVersionInfoSizeExA", "GetFileVersionInfoSizeExW", "GetFileVersionInfoSizeW",
    "GetFileVersionInfoW", "VerFindFileA", "VerFindFileW", "VerInstallFileA", "VerInstallFileW",
    "VerQueryValueA", "VerQueryValueW"};

static void LoadRealVersionDll() {
    wchar_t path[MAX_PATH];
    UINT n = GetSystemDirectoryW(path, MAX_PATH);
    if (!n || n > MAX_PATH - 20) return;
    wcscat_s(path, L"\\version.dll");
    HMODULE real = LoadLibraryW(path);
    if (!real) return;
    for (int i = 0; i < 15; i++) g_real[i] = (void*)GetProcAddress(real, kRealNames[i]);
}

// ---------------------------------------------------------------------------------- logging --
static void Log(const char* fmt, ...) {
    char path[MAX_PATH];
    DWORD n = GetTempPathA(MAX_PATH, path);
    if (!n || n > MAX_PATH - 20) return;
    strcat_s(path, "DominoLink.log");
    FILE* f = nullptr;
    if (fopen_s(&f, path, "a") || !f) return;
    SYSTEMTIME st;
    GetLocalTime(&st);
    fprintf(f, "%04d-%02d-%02d %02d:%02d:%02d [%lu] ", st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond,
            GetCurrentProcessId());
    va_list ap;
    va_start(ap, fmt);
    vfprintf(f, fmt, ap);
    va_end(ap);
    fputc('\n', f);
    fclose(f);
}

// --------------------------------------------------------------------------------- settings --
struct Settings {
    int amount = 1;      // pre-roll length; 0 = off
    int unit = 1;        // 0 = 16th notes, 1 = beats (quarter notes)
    int sendTempo = 1;   // send the tempo to FL Studio
};
static Settings g_set, g_pending;
static char g_ini[MAX_PATH];        // DominoLink.ini
static char g_syncIni[MAX_PATH];    // Domino's MidiSync.ini (for the time code port)
static bool g_newProfile = false;   // Domino has no settings for this Windows user yet

static bool IsDir(const char* p) {
    DWORD a = GetFileAttributesA(p);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY);
}

static void FindIniFiles() {
    char dir[MAX_PATH], user[128] = "";
    GetModuleFileNameA(nullptr, dir, MAX_PATH);
    if (char* slash = strrchr(dir, '\\')) *slash = 0;
    GetEnvironmentVariableA("USERNAME", user, sizeof user);
    char iniDir[MAX_PATH];
    sprintf_s(iniDir, "%s\\IniFiles\\%s", dir, user);   // where Domino keeps its own settings
    g_newProfile = user[0] && !IsDir(iniDir);
    if (!user[0] || !IsDir(iniDir)) strcpy_s(iniDir, dir);
    sprintf_s(g_ini, "%s\\DominoLink.ini", iniDir);
    sprintf_s(g_syncIni, "%s\\MidiSync.ini", iniDir);
}

static void LoadSettings() {
    g_set.amount = GetPrivateProfileIntA("Preroll", "Amount", 1, g_ini);
    g_set.unit = GetPrivateProfileIntA("Preroll", "Unit", 1, g_ini);
    g_set.sendTempo = GetPrivateProfileIntA("Tempo", "Send", 1, g_ini);
    if (g_set.amount < 0) g_set.amount = 0;
    if (g_set.amount > 64) g_set.amount = 64;
    if (g_set.unit != 0) g_set.unit = 1;
    g_set.sendTempo = g_set.sendTempo ? 1 : 0;
}

static void SaveSettings() {
    char v[16];
    sprintf_s(v, "%d", g_set.amount);
    WritePrivateProfileStringA("Preroll", "Amount", v, g_ini);
    WritePrivateProfileStringA("Preroll", "Unit", g_set.unit ? "1" : "0", g_ini);
    WritePrivateProfileStringA("Tempo", "Send", g_set.sendTempo ? "1" : "0", g_ini);
}

// ----------------------------------------------------------------------- Domino's internals --
// Found through the code of Domino's own Playback commands:
//   Play/Stop          sub rsp,38h / cmp byte [rcx+PLAYING],0 / je ...
//   Start of the Song  sub rsp,38h / mov r8b,1 / mov byte [rsp+20h],0 / xor edx,edx / call SetPlayhead
//   Previous Quantize  sub rsp,38h / mov edx,[quantize] / mov r9,rcx / mov rcx,[rcx+SONG] / call QuantizeTicks
//                      / mov edx,[r9+PLAYHEAD] ...;  QuantizeTicks: ... imul eax,[rcx+TIMEBASE] ...
typedef void (*SetPlayheadFn)(void* self, int tick, unsigned char a, void* unused, unsigned char b);
typedef void (*CommandFn)(void* self);

static struct {
    bool ok = false;
    int offPlaying = 0, offPlayhead = 0, offSong = 0, offTimebase = 0;
    SetPlayheadFn setPlayhead = nullptr;
    CommandFn playStop = nullptr;    // Domino's own Play/Stop handler
    void** playStopSlot = nullptr;   // its entry in Domino's message map
} g_dom;

static bool FindSection(BYTE* base, const char* name, BYTE** start, size_t* size) {
    auto dos = (IMAGE_DOS_HEADER*)base;
    auto nt = (IMAGE_NT_HEADERS*)(base + dos->e_lfanew);
    auto sec = IMAGE_FIRST_SECTION(nt);
    for (int i = 0; i < nt->FileHeader.NumberOfSections; i++, sec++) {
        if (strncmp((const char*)sec->Name, name, 8) == 0) {
            *start = base + sec->VirtualAddress;
            *size = sec->Misc.VirtualSize;
            return true;
        }
    }
    return false;
}

// MFC message map entry (x64): nMessage, nCode, nID, nLastID (4 bytes each), nSig (8), pfn (8)
static BYTE* FindCommandEntry(BYTE* start, size_t size, UINT id) {
    const UINT pattern[4] = {WM_COMMAND, 0, id, id};
    for (size_t i = 0; i + 32 <= size; i += 4)
        if (memcmp(start + i, pattern, 16) == 0) return start + i;
    return nullptr;
}

static int HexDigit(char c) {
    return c >= '0' && c <= '9' ? c - '0' : c >= 'A' && c <= 'F' ? c - 'A' + 10 : c >= 'a' && c <= 'f' ? c - 'a' + 10 : -1;
}

static bool Bytes(const BYTE* p, const char* hex) {   // "48 83 EC 38" (".." = any byte)
    for (const char* h = hex; *h;) {
        while (*h == ' ') h++;
        if (!*h) break;
        if (h[0] != '.' && HexDigit(h[0]) * 16 + HexDigit(h[1]) != *p) return false;
        h += 2;
        p++;
    }
    return true;
}

static bool InImage(const void* p) {
    BYTE* base = (BYTE*)GetModuleHandleA(nullptr);
    auto nt = (IMAGE_NT_HEADERS*)(base + ((IMAGE_DOS_HEADER*)base)->e_lfanew);
    return (BYTE*)p >= base && (BYTE*)p < base + nt->OptionalHeader.SizeOfImage;
}

static bool FindInternals() {
    BYTE* base = (BYTE*)GetModuleHandleA(nullptr);
    BYTE* rdata;
    size_t rdataSize;
    if (!FindSection(base, ".rdata", &rdata, &rdataSize)) return Log("pre-roll off: no .rdata section"), false;
    BYTE* ePlay = FindCommandEntry(rdata, rdataSize, 32886);   // Play/Stop
    BYTE* eStart = FindCommandEntry(rdata, rdataSize, 32894);  // Start of the Song
    BYTE* ePrev = FindCommandEntry(rdata, rdataSize, 33326);   // Previous Quantize Unit
    if (!ePlay || !eStart || !ePrev) return Log("pre-roll off: Playback commands not found"), false;
    BYTE* fPlay = *(BYTE**)(ePlay + 24);
    BYTE* fStart = *(BYTE**)(eStart + 24);
    BYTE* fPrev = *(BYTE**)(ePrev + 24);
    if (!InImage(fPlay) || !InImage(fStart) || !InImage(fPrev)) return Log("pre-roll off: handlers outside Domino"), false;
    if (!Bytes(fPlay, "48 83 EC 38 80 B9 .. .. .. .. 00 74"))
        return Log("pre-roll off: Play/Stop doesn't match"), false;
    if (!Bytes(fStart, "48 83 EC 38 41 B0 01 C6 44 24 20 00 33 D2 E8"))
        return Log("pre-roll off: Start of the Song doesn't match"), false;
    if (!Bytes(fPrev, "48 83 EC 38 8B 15 .. .. .. .. 4C 8B C9 48 8B 89 .. .. .. .. E8 .. .. .. .. 41 8B 91"))
        return Log("pre-roll off: Previous Quantize Unit doesn't match"), false;
    BYTE* fQuant = fPrev + 25 + *(int*)(fPrev + 21);
    int offTimebase = -1;
    for (int i = 0; i < 40; i++)
        if (fQuant[i] == 0x0F && fQuant[i + 1] == 0xAF && fQuant[i + 2] == 0x41) {   // imul eax,[rcx+disp8]
            offTimebase = fQuant[i + 3];
            break;
        }
    if (offTimebase < 0) return Log("pre-roll off: timebase not found"), false;
    g_dom.offPlaying = *(int*)(fPlay + 6);
    g_dom.offSong = *(int*)(fPrev + 16);
    g_dom.offPlayhead = *(int*)(fPrev + 28);
    g_dom.offTimebase = offTimebase;
    g_dom.setPlayhead = (SetPlayheadFn)(fStart + 19 + *(int*)(fStart + 15));
    g_dom.playStop = (CommandFn)fPlay;
    g_dom.playStopSlot = (void**)(ePlay + 24);
    if (g_dom.offPlaying <= 0 || g_dom.offPlaying > 0x10000 || g_dom.offPlayhead <= 0 || g_dom.offPlayhead > 0x10000 ||
        g_dom.offSong <= 0 || g_dom.offSong > 0x10000)
        return Log("pre-roll off: unexpected offsets"), false;
    Log("Domino internals: playing +%#x, playhead +%#x, song +%#x, timebase +%#x", g_dom.offPlaying, g_dom.offPlayhead,
        g_dom.offSong, g_dom.offTimebase);
    return true;
}

// ---------------------------------------------------------------------------------- pre-roll --
static struct {
    bool pending = false;    // a pre-rolled playback that hasn't been cleaned up yet
    bool seenPlaying = false;
    void* self = nullptr;
    int orig = 0;            // where the playhead was
    int start = 0;           // where playback started
    ULONGLONG since = 0;
} g_pre;
static UINT_PTR g_timer = 0;

static int PrerollTicks(void* self) {
    if (g_set.amount <= 0) return 0;
    BYTE* song = *(BYTE**)((BYTE*)self + g_dom.offSong);
    if (!song) return 0;
    int timebase = *(int*)(song + g_dom.offTimebase);
    if (timebase < 24 || timebase > 100000) return 0;
    return g_set.unit == 0 ? g_set.amount * timebase / 4 : g_set.amount * timebase;
}

static void FinishPreroll() {
    if (!g_pre.pending) return;
    g_pre.pending = false;
    int now = *(int*)((BYTE*)g_pre.self + g_dom.offPlayhead);
    if (now == g_pre.start)   // Domino put the playhead back where playback started: back to your spot
        g_dom.setPlayhead(g_pre.self, g_pre.orig, 1, nullptr, 0);
}

static VOID CALLBACK PrerollTimer(HWND, UINT, UINT_PTR id, DWORD) {
    if (g_pre.pending) {
        bool playing = ((BYTE*)g_pre.self)[g_dom.offPlaying] != 0;
        if (playing) {
            g_pre.seenPlaying = true;
            return;
        }
        if (!g_pre.seenPlaying && GetTickCount64() - g_pre.since < 1000) return;   // not started yet
        FinishPreroll();
    }
    KillTimer(nullptr, id);
    g_timer = 0;
}

static void PlayStopHook(void* self) {
    BYTE* s = (BYTE*)self;
    if (!s[g_dom.offPlaying]) {   // about to start: step back first
        if (g_pre.pending && g_pre.self == self) FinishPreroll();
        int ticks = PrerollTicks(self);
        int cur = *(int*)(s + g_dom.offPlayhead);
        int target = cur > ticks ? cur - ticks : 0;
        if (ticks > 0 && target != cur) {
            g_dom.setPlayhead(self, target, 1, nullptr, 0);
            g_pre.pending = true;
            g_pre.seenPlaying = false;
            g_pre.self = self;
            g_pre.orig = cur;
            g_pre.start = *(int*)(s + g_dom.offPlayhead);
            g_pre.since = GetTickCount64();
            if (!g_timer) g_timer = SetTimer(nullptr, 0, 50, PrerollTimer);
        }
    }
    g_dom.playStop(self);
}

static void InstallPreroll() {
    if (!FindInternals()) return;
    DWORD old;
    if (!VirtualProtect(g_dom.playStopSlot, sizeof(void*), PAGE_READWRITE, &old)) return Log("pre-roll off: can't patch");
    *g_dom.playStopSlot = (void*)&PlayStopHook;
    VirtualProtect(g_dom.playStopSlot, sizeof(void*), old, &old);
    g_dom.ok = true;
    Log("pre-roll on");
}

// ------------------------------------------------------------------------- tempo for FL --
static CRITICAL_SECTION g_ticksLock;
static std::vector<double> g_ticks;     // clock tick times waiting for the tempo thread
static HANDLE g_ticksEvent = nullptr;
static HMIDIOUT g_clockOut = nullptr;   // the one Domino port whose clock ticks are measured
static double g_qpcScale = 0;

static HMIDIOUT g_dominoSyncOut = nullptr;   // Domino's own handle on its time code port (a port can't be
                                             // opened twice in one program, so the tempo goes out through it)
static char g_syncPort[MAXPNAMELEN] = "SysEx";

typedef MMRESULT(WINAPI* MidiOutShortMsgFn)(HMIDIOUT, DWORD);
typedef MMRESULT(WINAPI* MidiOutCloseFn)(HMIDIOUT);
typedef MMRESULT(WINAPI* MidiOutOpenFn)(LPHMIDIOUT, UINT, DWORD_PTR, DWORD_PTR, DWORD);
static MidiOutShortMsgFn g_realShortMsg = nullptr;
static MidiOutCloseFn g_realClose = nullptr;
static MidiOutOpenFn g_realOpen = nullptr;

static MMRESULT WINAPI HookMidiOutOpen(LPHMIDIOUT out, UINT device, DWORD_PTR cb, DWORD_PTR inst, DWORD flags) {
    MMRESULT r = g_realOpen(out, device, cb, inst, flags);
    MIDIOUTCAPSA caps;
    if (r == MMSYSERR_NOERROR && out && midiOutGetDevCapsA(device, &caps, sizeof caps) == MMSYSERR_NOERROR &&
        strcmp(caps.szPname, g_syncPort) == 0)
        g_dominoSyncOut = *out;
    return r;
}

static MMRESULT WINAPI HookMidiOutShortMsg(HMIDIOUT h, DWORD msg) {
    if ((msg & 0xFF) == 0xF8 && g_set.sendTempo && g_ticksEvent) {   // MIDI clock (Domino sends it to every port)
        if (!g_clockOut) g_clockOut = h;
        if (h == g_clockOut) {
            LARGE_INTEGER t;
            QueryPerformanceCounter(&t);
            EnterCriticalSection(&g_ticksLock);
            g_ticks.push_back(t.QuadPart * g_qpcScale);
            LeaveCriticalSection(&g_ticksLock);
            SetEvent(g_ticksEvent);
        }
    }
    return g_realShortMsg(h, msg);
}

static MMRESULT WINAPI HookMidiOutClose(HMIDIOUT h) {
    if (h == g_clockOut) g_clockOut = nullptr;
    if (h == g_dominoSyncOut) g_dominoSyncOut = nullptr;
    return g_realClose(h);
}

static HMIDIOUT OpenSyncPort() {   // only used while Domino doesn't have the port open itself
    UINT n = midiOutGetNumDevs();
    for (UINT i = 0; i < n; i++) {
        MIDIOUTCAPSA caps;
        if (midiOutGetDevCapsA(i, &caps, sizeof caps) == MMSYSERR_NOERROR && strcmp(caps.szPname, g_syncPort) == 0) {
            HMIDIOUT h = nullptr;
            if (g_realOpen(&h, i, 0, 0, CALLBACK_NULL) == MMSYSERR_NOERROR) return h;
        }
    }
    Log("tempo: can't open MIDI port \"%s\"", g_syncPort);
    return nullptr;
}

static void SendTempo(HMIDIOUT h, double bpm) {
    int v = (int)(bpm * 100 + 0.5);
    BYTE data[7] = {0xF0, 0x7D, 0x10, (BYTE)((v >> 14) & 0x7F), (BYTE)((v >> 7) & 0x7F), (BYTE)(v & 0x7F), 0xF7};
    MIDIHDR hdr = {};
    hdr.lpData = (LPSTR)data;
    hdr.dwBufferLength = sizeof data;
    if (midiOutPrepareHeader(h, &hdr, sizeof hdr) != MMSYSERR_NOERROR) return;
    if (midiOutLongMsg(h, &hdr, sizeof hdr) == MMSYSERR_NOERROR)
        for (int i = 0; i < 100 && !(hdr.dwFlags & MHDR_DONE); i++) Sleep(1);
    midiOutUnprepareHeader(h, &hdr, sizeof hdr);
}

static DWORD WINAPI TempoThread(LPVOID) {
    TempoReader reader;
    std::vector<double> batch;
    HMIDIOUT own = nullptr;
    ULONGLONG lastTry = 0;
    bool logged = false;
    for (;;) {
        WaitForSingleObject(g_ticksEvent, 1000);
        EnterCriticalSection(&g_ticksLock);
        batch.swap(g_ticks);
        LeaveCriticalSection(&g_ticksLock);
        for (double t : batch) {
            double bpm;
            if (!reader.feed(t, bpm)) continue;
            HMIDIOUT out = g_dominoSyncOut;
            if (!out) {
                if (!own && GetTickCount64() - lastTry > 5000) {
                    lastTry = GetTickCount64();
                    own = OpenSyncPort();
                }
                out = own;
            } else if (own) {
                midiOutClose(own);
                own = nullptr;
            }
            if (!out) continue;
            if (!logged) {
                Log("tempo goes to MIDI port \"%s\" (%s handle)", g_syncPort, out == own ? "own" : "Domino's");
                logged = true;
            }
            SendTempo(out, bpm);
        }
        batch.clear();
    }
}

// ------------------------------------------------------------ settings on the Sync page --
enum {
    ID_GROUP = 0x7D40, ID_LABEL, ID_AMOUNT, ID_SPIN, ID_UNIT, ID_TEMPO, ID_NOTE
};
static HWND g_prefRoot = nullptr;   // the Preferences window our controls belong to
static const char* kOrigProc = "DominoLinkOrigProc";

static LRESULT CALLBACK SyncPageProc(HWND page, UINT msg, WPARAM wp, LPARAM lp) {
    WNDPROC orig = (WNDPROC)GetPropA(page, kOrigProc);
    if (msg == WM_COMMAND) {
        int id = LOWORD(wp), code = HIWORD(wp);
        if (id == ID_AMOUNT && code == EN_CHANGE) {
            char t[16];
            GetWindowTextA((HWND)lp, t, sizeof t);
            int v = atoi(t);
            g_pending.amount = v < 0 ? 0 : v > 64 ? 64 : v;
        } else if (id == ID_UNIT && code == CBN_SELCHANGE) {
            g_pending.unit = SendMessageA((HWND)lp, CB_GETCURSEL, 0, 0) == 0 ? 0 : 1;
        } else if (id == ID_TEMPO && code == BN_CLICKED) {
            g_pending.sendTempo = SendMessageA((HWND)lp, BM_GETCHECK, 0, 0) == BST_CHECKED;
        }
    } else if (msg == WM_NCDESTROY) {
        SetWindowLongPtrA(page, GWLP_WNDPROC, (LONG_PTR)orig);
        RemovePropA(page, kOrigProc);
    }
    return CallWindowProcA(orig, page, msg, wp, lp);
}

static HWND AddControl(HWND page, DWORD exStyle, const wchar_t* cls, const wchar_t* text, DWORD style, int x, int y, int w,
                       int h, int id, HFONT font) {
    RECT r = {x, y, x + w, y + h};
    MapDialogRect(page, &r);
    HWND c = CreateWindowExW(exStyle, cls, text, WS_CHILD | WS_VISIBLE | style, r.left, r.top, r.right - r.left,
                             r.bottom - r.top, page, (HMENU)(INT_PTR)id, GetModuleHandleW(nullptr), nullptr);
    if (c && font) SendMessageW(c, WM_SETFONT, (WPARAM)font, FALSE);
    return c;
}

static void AddSyncPageControls(HWND page) {
    HWND root = GetAncestor(page, GA_ROOT);
    if (root != g_prefRoot) {   // a new Preferences window: start from the saved settings
        g_prefRoot = root;
        g_pending = g_set;
    }
    HFONT font = (HFONT)SendMessageW(page, WM_GETFONT, 0, 0);
    AddControl(page, 0, L"BUTTON", L"FL Studio link (Domino Link add-on " ADDON_VERSION ")", BS_GROUPBOX, 0, 135, 257, 60,
               ID_GROUP, font);
    AddControl(page, 0, L"STATIC", L"&Pre-roll on Play: ", SS_RIGHT | SS_CENTERIMAGE, 5, 150, 108, 12, ID_LABEL, font);
    HWND amount = AddControl(page, WS_EX_CLIENTEDGE, L"EDIT", L"", ES_NUMBER | ES_AUTOHSCROLL | WS_TABSTOP, 113, 149,
                             28, 13, ID_AMOUNT, font);
    HWND spin = AddControl(page, 0, UPDOWN_CLASSW, L"",
                           UDS_SETBUDDYINT | UDS_ALIGNRIGHT | UDS_ARROWKEYS | UDS_NOTHOUSANDS, 141, 149, 10, 13, ID_SPIN,
                           nullptr);
    HWND unit = AddControl(page, 0, L"COMBOBOX", L"", CBS_DROPDOWNLIST | WS_VSCROLL | WS_TABSTOP, 150, 149, 98, 60,
                           ID_UNIT, font);
    HWND tempo = AddControl(page, 0, L"BUTTON", L"&Send the tempo to FL Studio (needs the timing clock above)",
                            BS_AUTOCHECKBOX | WS_TABSTOP, 5, 166, 245, 10, ID_TEMPO, font);
    AddControl(page, 0, L"STATIC",
               g_dom.ok ? L"Play/Stop (Space) starts this far before the playhead. 0 = off."
                        : L"Pre-roll isn't available for this version of Domino.",
               SS_LEFT, 5, 179, 245, 10, ID_NOTE, font);
    if (spin && amount) {
        SendMessageW(spin, UDM_SETBUDDY, (WPARAM)amount, 0);
        SendMessageW(spin, UDM_SETRANGE32, 0, 64);
        SendMessageW(spin, UDM_SETPOS32, 0, g_pending.amount);
    }
    if (unit) {
        SendMessageW(unit, CB_ADDSTRING, 0, (LPARAM)L"16th note(s)");
        SendMessageW(unit, CB_ADDSTRING, 0, (LPARAM)L"beat(s)");
        SendMessageW(unit, CB_SETCURSEL, g_pending.unit, 0);
    }
    if (tempo) SendMessageW(tempo, BM_SETCHECK, g_pending.sendTempo ? BST_CHECKED : BST_UNCHECKED, 0);
    if (!g_dom.ok) {
        EnableWindow(amount, FALSE);
        EnableWindow(spin, FALSE);
        EnableWindow(unit, FALSE);
    }
    SetPropA(page, kOrigProc, (HANDLE)GetWindowLongPtrA(page, GWLP_WNDPROC));
    SetWindowLongPtrA(page, GWLP_WNDPROC, (LONG_PTR)SyncPageProc);
}

static LRESULT CALLBACK AfterWndProcHook(int code, WPARAM wp, LPARAM lp) {
    if (code == HC_ACTION) {
        auto c = (CWPRETSTRUCT*)lp;
        // Domino's Sync page: has "Enable MTC Master", "Enable MMC Slave" and "Broadcast timing clock"
        if (c->message == WM_INITDIALOG && GetDlgItem(c->hwnd, 1420) && GetDlgItem(c->hwnd, 1423) &&
            GetDlgItem(c->hwnd, 1466) && !GetDlgItem(c->hwnd, ID_GROUP))
            AddSyncPageControls(c->hwnd);
    }
    return CallNextHookEx(nullptr, code, wp, lp);
}

static LRESULT CALLBACK BeforeWndProcHook(int code, WPARAM wp, LPARAM lp) {
    if (code == HC_ACTION) {
        auto c = (CWPSTRUCT*)lp;
        if (c->message == WM_COMMAND && g_prefRoot && c->hwnd == g_prefRoot && HIWORD(c->wParam) == BN_CLICKED) {
            if (LOWORD(c->wParam) == IDOK) {   // Preferences closed with OK: keep our settings too
                g_set = g_pending;
                SaveSettings();
                g_prefRoot = nullptr;
                Log("settings saved: pre-roll %d %s, tempo %s", g_set.amount, g_set.unit ? "beat(s)" : "16th(s)",
                    g_set.sendTempo ? "on" : "off");
            } else if (LOWORD(c->wParam) == IDCANCEL) {
                g_prefRoot = nullptr;
            }
        }
    }
    return CallNextHookEx(nullptr, code, wp, lp);
}

// ------------------------------------------------------------------ first start of Domino --
// Domino keeps its preferences per Windows user (IniFiles\<user>) and gives a new user its defaults. On
// that first start, once the main window is up, the add-on asks whether to load DominoLink.dmc. Yes does
// what File > Import Preferences does: start Domino again with /config"<file>" /wp<pid> and close this
// one; the new Domino waits for it, replaces IniFiles\<user> with the file's contents and starts.
static UINT_PTR g_firstStartTimer = 0;
static int g_firstStartTries = 0;

static BOOL CALLBACK FindMainWindow(HWND w, LPARAM out) {
    char title[256];
    if (GetWindowThreadProcessId(w, nullptr) != GetCurrentThreadId() || !IsWindowVisible(w) || GetWindow(w, GW_OWNER))
        return TRUE;
    int n = GetWindowTextA(w, title, sizeof title);
    if (n < 6 || strcmp(title + n - 6, "Domino") != 0) return TRUE;   // "Untitled [noname.dms] - Domino"
    *(HWND*)out = w;
    return FALSE;
}

static VOID CALLBACK FirstStartTimer(HWND, UINT, UINT_PTR, DWORD) {
    HWND main = nullptr;
    EnumWindows(FindMainWindow, (LPARAM)&main);
    if (!main && ++g_firstStartTries < 120) return;   // wait up to 30 s for the main window
    KillTimer(nullptr, g_firstStartTimer);
    if (!main) return;

    char exe[MAX_PATH], dmc[MAX_PATH], rel[MAX_PATH];
    GetModuleFileNameA(nullptr, exe, MAX_PATH);
    strcpy_s(rel, exe);
    if (char* slash = strrchr(rel, '\\')) *slash = 0;
    strcat_s(rel, "\\..\\setup\\domino-settings\\DominoLink.dmc");
    if (!GetFullPathNameA(rel, MAX_PATH, dmc, nullptr) || GetFileAttributesA(dmc) == INVALID_FILE_ATTRIBUTES) {
        Log("first start: no %s, not asking", rel);
        return;
    }
    char msg[1024];
    sprintf_s(msg,
              "This is Domino's first start for this Windows user, so it has its default settings.\n\n"
              "Load the Domino Link settings now? They set up the MIDI-OUT ports, the sync with FL Studio "
              "and the pre-roll. Domino restarts with them.\n\n"
              "You can also do it later: File > Import Preferences >\n%s",
              dmc);
    if (MessageBoxA(main, msg, "Domino Link", MB_YESNO | MB_ICONQUESTION) != IDYES) {
        Log("first start: settings not loaded");
        return;
    }
    char cmd[3 * MAX_PATH];
    sprintf_s(cmd, "\"%s\" /config\"%s\" /wp%lu", exe, dmc, GetCurrentProcessId());
    STARTUPINFOA si = {sizeof si};
    PROCESS_INFORMATION pi;
    if (!CreateProcessA(exe, cmd, nullptr, nullptr, FALSE, 0, nullptr, nullptr, &si, &pi)) {
        Log("first start: couldn't start Domino again (error %lu)", GetLastError());
        return;
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    Log("first start: loading %s", dmc);
    PostMessageA(main, WM_CLOSE, 0, 0);
}

// ------------------------------------------------------------------------------ start-up --
static DWORD g_mainThread = 0;
static bool g_uiReady = false;
typedef BOOL(WINAPI* GetMessageAFn)(LPMSG, HWND, UINT, UINT);
typedef BOOL(WINAPI* PeekMessageAFn)(LPMSG, HWND, UINT, UINT, UINT);
static GetMessageAFn g_realGetMessageA = nullptr;
static PeekMessageAFn g_realPeekMessageA = nullptr;

static void UiStart() {   // first time Domino's message loop runs, on its UI thread
    if (g_uiReady || GetCurrentThreadId() != g_mainThread) return;
    g_uiReady = true;
    InstallPreroll();
    SetWindowsHookExA(WH_CALLWNDPROCRET, AfterWndProcHook, nullptr, g_mainThread);
    SetWindowsHookExA(WH_CALLWNDPROC, BeforeWndProcHook, nullptr, g_mainThread);
    if (HANDLE t = CreateThread(nullptr, 0, TempoThread, nullptr, 0, nullptr)) CloseHandle(t);
    if (g_newProfile && !strstr(GetCommandLineA(), "/config"))   // not while Domino imports or exports settings
        g_firstStartTimer = SetTimer(nullptr, 0, 250, FirstStartTimer);
}

static BOOL WINAPI HookGetMessageA(LPMSG m, HWND h, UINT a, UINT b) {
    UiStart();
    return g_realGetMessageA(m, h, a, b);
}

static BOOL WINAPI HookPeekMessageA(LPMSG m, HWND h, UINT a, UINT b, UINT r) {
    UiStart();
    return g_realPeekMessageA(m, h, a, b, r);
}

// Point Domino.exe's import of dll!func at hook; returns the original function.
static void* PatchImport(const char* dll, const char* func, void* hook) {
    BYTE* base = (BYTE*)GetModuleHandleA(nullptr);
    auto dos = (IMAGE_DOS_HEADER*)base;
    auto nt = (IMAGE_NT_HEADERS*)(base + dos->e_lfanew);
    auto& dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (!dir.VirtualAddress) return nullptr;
    for (auto imp = (IMAGE_IMPORT_DESCRIPTOR*)(base + dir.VirtualAddress); imp->Name; imp++) {
        if (_stricmp((const char*)(base + imp->Name), dll) != 0) continue;
        auto names = (IMAGE_THUNK_DATA*)(base + (imp->OriginalFirstThunk ? imp->OriginalFirstThunk : imp->FirstThunk));
        auto slots = (IMAGE_THUNK_DATA*)(base + imp->FirstThunk);
        for (; names->u1.AddressOfData; names++, slots++) {
            if (IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal)) continue;
            auto ibn = (IMAGE_IMPORT_BY_NAME*)(base + names->u1.AddressOfData);
            if (strcmp((const char*)ibn->Name, func) != 0) continue;
            if (InImage((void*)slots->u1.Function)) return nullptr;   // not filled in by Windows yet
            DWORD old;
            if (!VirtualProtect(&slots->u1.Function, sizeof(void*), PAGE_READWRITE, &old)) return nullptr;
            void* orig = (void*)slots->u1.Function;
            slots->u1.Function = (ULONG_PTR)hook;
            VirtualProtect(&slots->u1.Function, sizeof(void*), old, &old);
            return orig;
        }
    }
    return nullptr;
}

static bool InsideDomino() {
    char exe[MAX_PATH];
    GetModuleFileNameA(nullptr, exe, MAX_PATH);
    const char* name = strrchr(exe, '\\');
    return _stricmp(name ? name + 1 : exe, "Domino.exe") == 0;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason != DLL_PROCESS_ATTACH) return TRUE;
    DisableThreadLibraryCalls(instance);
    LoadRealVersionDll();
    if (!InsideDomino()) return TRUE;
    g_mainThread = GetCurrentThreadId();
    LARGE_INTEGER f;
    QueryPerformanceFrequency(&f);
    g_qpcScale = 1.0 / (double)f.QuadPart;
    InitializeCriticalSection(&g_ticksLock);
    g_ticksEvent = CreateEventA(nullptr, FALSE, FALSE, nullptr);
    FindIniFiles();
    LoadSettings();
    GetPrivateProfileStringA("MTCMaster", "MidiDeviceName", "SysEx", g_syncPort, sizeof g_syncPort, g_syncIni);
    g_realOpen = (MidiOutOpenFn)PatchImport("WINMM.dll", "midiOutOpen", (void*)&HookMidiOutOpen);
    if (!g_realOpen) g_realOpen = (MidiOutOpenFn)GetProcAddress(GetModuleHandleA("winmm.dll"), "midiOutOpen");
    g_realGetMessageA = (GetMessageAFn)PatchImport("USER32.dll", "GetMessageA", (void*)&HookGetMessageA);
    g_realPeekMessageA = (PeekMessageAFn)PatchImport("USER32.dll", "PeekMessageA", (void*)&HookPeekMessageA);
    g_realShortMsg = (MidiOutShortMsgFn)PatchImport("WINMM.dll", "midiOutShortMsg", (void*)&HookMidiOutShortMsg);
    g_realClose = (MidiOutCloseFn)PatchImport("WINMM.dll", "midiOutClose", (void*)&HookMidiOutClose);
    if (!g_realShortMsg) g_realShortMsg = (MidiOutShortMsgFn)GetProcAddress(GetModuleHandleA("winmm.dll"), "midiOutShortMsg");
    if (!g_realClose) g_realClose = (MidiOutCloseFn)GetProcAddress(GetModuleHandleA("winmm.dll"), "midiOutClose");
    Log("Domino Link add-on " ADDON_VERSION " loaded (settings: %s; message loop hook %s; MIDI hook %s)", g_ini,
        g_realGetMessageA || g_realPeekMessageA ? "ok" : "MISSING", g_realShortMsg ? "ok" : "MISSING");
    return TRUE;
}
