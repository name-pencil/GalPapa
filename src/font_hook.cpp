#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string>
#include <vector>
#include <cstring>

static std::wstring base;
static std::vector<wchar_t> mapping;
static decltype(&TextOutA) originalTextOut = TextOutA;
static decltype(&CreateWindowExA) originalCreateWindow = CreateWindowExA;
static decltype(&SendMessageA) originalSendMessage = SendMessageA;
static CRITICAL_SECTION guard;
struct CachedFont { LOGFONTW spec; HFONT font; };
static std::vector<CachedFont> fonts;
static std::vector<std::wstring> loggedMetrics;
static HFONT Cached(const LOGFONTW& spec) {
    for (const auto& entry : fonts) if (!memcmp(&entry.spec, &spec, sizeof(spec))) return entry.font;
    HFONT font = CreateFontIndirectW(&spec);
    if (font) fonts.push_back({spec, font});
    return font;
}
static bool GlyphMetrics(HDC dc, wchar_t c, GLYPHMETRICS& metrics) {
    MAT2 matrix{}; matrix.eM11.value = matrix.eM22.value = 1;
    return GetGlyphOutlineW(dc, c, GGO_METRICS, &metrics, 0, nullptr, &matrix) != GDI_ERROR;
}
// Called with the Paperlogy font selected and guard held. The engine allocates a
// fixed half-width cell to ASCII, irrespective of the selected font's advance.
static int FitAscii(HDC dc, wchar_t c, LOGFONTW spec) {
    const int fullCell = abs(spec.lfHeight);
    const int cell = fullCell / 2;
    const int margin = (fullCell / 20 > 2) ? fullCell / 20 : 2;
    const int available = (cell - margin > 1) ? cell - margin : 1;
    GLYPHMETRICS metrics{};
    if (!GlyphMetrics(dc, c, metrics)) return 0;
    if ((int)metrics.gmBlackBoxX > available) {
        TEXTMETRICW tm{}; GetTextMetricsW(dc, &tm);
        spec.lfWidth = (tm.tmAveCharWidth * available) / (int)metrics.gmBlackBoxX;
        if (spec.lfWidth < 1) spec.lfWidth = 1;
        while (spec.lfWidth > 0) {
            HFONT fitted = Cached(spec);
            if (!fitted) break;
            SelectObject(dc, fitted);
            if (!GlyphMetrics(dc, c, metrics) || (int)metrics.gmBlackBoxX <= available) break;
            --spec.lfWidth;
        }
    }
    // Align the ink to the cell's left edge. The engine advances the pen itself;
    // adding an extra proportional-font bearing can consume the inter-cell gap.
    return -metrics.gmptGlyphOrigin.x;
}
static void Log(const std::string& text) {
#ifdef GALPAPA_DIAGNOSTICS
    HANDLE f = CreateFileW((base + L"font_hook.log").c_str(), FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS, 0, nullptr);
    if (f != INVALID_HANDLE_VALUE) {
        DWORD n; WriteFile(f, text.data(), (DWORD)text.size(), &n, nullptr); CloseHandle(f);
    }
#endif
}
static std::string Utf8(const std::wstring& s) {
    int n = WideCharToMultiByte(CP_UTF8, 0, s.data(), (int)s.size(), nullptr, 0, nullptr, nullptr);
    std::string result(n, '\0');
    WideCharToMultiByte(CP_UTF8, 0, s.data(), (int)s.size(), &result[0], n, nullptr, nullptr);
    return result;
}
static std::wstring DecodeText(LPCSTR text) {
    if (!text) return {};
    int count = (int)strlen(text);
    int n = MultiByteToWideChar(932, 0, text, count, nullptr, 0);
    std::wstring wide(n, L'\0');
    if (n) MultiByteToWideChar(932, 0, text, count, &wide[0], n);
    for (auto& c : wide) {
        unsigned index = (unsigned)c - 0xe000;
        if (index < mapping.size()) c = mapping[index];
    }
    return wide;
}
static std::wstring SystemText(LPCSTR text) {
    auto wide = DecodeText(text);
    if (wide == L"終了します。よろしいですか？" ||
        wide == L"ゲームを終了します。よろしいですか？") return L"게임을 종료하시겠습니까?";
    if (wide == L"質問" || wide == L"確認") return L"확인";
    if (wide == L"終了") return L"종료";
    if (wide == L"警告") return L"경고";
    if (wide == L"情報") return L"알림";
    if (wide == L"エラー") return L"오류";
    return wide;
}
static int WINAPI UnicodeMessageBox(HWND window, LPCSTR text, LPCSTR caption, UINT type) {
    auto body = SystemText(text), title = SystemText(caption);
    Log("message_box title=" + Utf8(title) + " body=" + Utf8(body) + "\r\n");
    return MessageBoxW(window, text ? body.c_str() : nullptr, caption ? title.c_str() : nullptr, type);
}
static BOOL WINAPI UnicodeSetWindowText(HWND window, LPCSTR text) {
    auto wide = DecodeText(text);
    const std::wstring japaneseTitle = L"ギャルとパパ活！ ～ヤリチン中年おぢのエンジョイPacoPacoライフ～";
    if (wide.compare(0, japaneseTitle.size(), japaneseTitle) == 0) {
        wide.replace(0, japaneseTitle.size(), L"갸루와 파파카츠! ～난봉꾼 중년 아저씨의 즐거운 파코파코 라이프～");
    }
    // Use the public Unicode API so Windows also updates the externally visible
    // caption cache and non-client frame, rather than only calling DefWindowProc.
    BOOL result = SetWindowTextW(window, wide.c_str());
    Log("window_title=" + Utf8(wide) + " ok=" + std::to_string(result) + "\r\n");
    return result;
}
static LRESULT WINAPI UnicodeSendMessage(HWND window, UINT message, WPARAM wparam, LPARAM lparam) {
    if (message == WM_SETTEXT) {
        Log("send_message_settext\r\n");
        return UnicodeSetWindowText(window, (LPCSTR)lparam);
    }
    return originalSendMessage(window, message, wparam, lparam);
}
static HWND WINAPI UnicodeCreateWindow(DWORD ex, LPCSTR cls, LPCSTR title, DWORD style,
    int x, int y, int width, int height, HWND parent, HMENU menu, HINSTANCE instance, LPVOID param) {
    // Keep ANSI class registration and message dispatch; only the caption is Unicode.
    HWND window = originalCreateWindow(ex, cls, title, style, x, y, width, height, parent, menu, instance, param);
    if (window && (ULONG_PTR)title > 0xffff) UnicodeSetWindowText(window, title);
    return window;
}
static int SymbolOffset(HDC dc, wchar_t c) {
    // Parentheses already have appropriate bearings for the engine's layout;
    // moving them toward the cell center crowds the adjacent Korean letters.
    if (c == L'（' || c == L'）' || c == L'(' || c == L')') return 0;
    WORD type1 = 0, type3 = 0;
    GetStringTypeW(CT_CTYPE1, &c, 1, &type1);
    GetStringTypeW(CT_CTYPE3, &c, 1, &type3);
    if (!(type1 & C1_PUNCT) && !(type3 & C3_SYMBOL)) return 0;
    MAT2 matrix{}; matrix.eM11.value = matrix.eM22.value = 1;
    GLYPHMETRICS glyph{}, reference{};
    if (GetGlyphOutlineW(dc, c, GGO_METRICS, &glyph, 0, nullptr, &matrix) == GDI_ERROR ||
        GetGlyphOutlineW(dc, L'가', GGO_METRICS, &reference, 0, nullptr, &matrix) == GDI_ERROR ||
        !glyph.gmBlackBoxX) return 0;
    int referenceCenter2 = 2 * reference.gmptGlyphOrigin.x + reference.gmBlackBoxX;
    if (c == L'『' || c == L'』') {
        LOGFONTW spec{};
        GetObjectW(GetCurrentObject(dc, OBJ_FONT), sizeof(spec), &spec);
        referenceCenter2 = abs(spec.lfHeight); // Twice the center of the full-width engine cell.
    }
    int symbolCenter2 = 2 * glyph.gmptGlyphOrigin.x + glyph.gmBlackBoxX;
    int shift = (referenceCenter2 - symbolCenter2) / 2;
    // Negative shifts can clip the left edge of the glyph bitmap. Wider symbols
    // retain their original position; narrow punctuation moves into the center.
    return shift > 0 ? shift : 0;
}
static BOOL WINAPI KoreanTextOut(HDC dc, int x, int y, LPCSTR text, int count) {
    if (!text || count <= 0) return originalTextOut(dc, x, y, text, count);
    int n = MultiByteToWideChar(932, 0, text, count, nullptr, 0);
    std::wstring wide(n, L'\0');
    MultiByteToWideChar(932, 0, text, count, &wide[0], n);
    bool korean = false;
    for (auto& c : wide) {
        unsigned index = (unsigned)c - 0xe000;
        if (index < mapping.size()) { c = mapping[index]; korean = true; }
    }
    const bool asciiGlyph = wide.size() == 1 && wide[0] >= L'!' && wide[0] <= L'~';
    // Untouched Japanese (including old save titles) is CP932 too. Calling
    // TextOutA here decodes it through the PC's CP949 locale and corrupts it.
    // Retain the current font and metrics, but pass the decoded Unicode text.
    if (!korean && !asciiGlyph) return TextOutW(dc, x, y, wide.data(), (int)wide.size());
    EnterCriticalSection(&guard);
    LOGFONTW lf{};
    GetObjectW(GetCurrentObject(dc, OBJ_FONT), sizeof(lf), &lf);
    lf.lfWidth = 0;
    lf.lfWeight = FW_NORMAL;
    lf.lfCharSet = DEFAULT_CHARSET;
    wcscpy_s(lf.lfFaceName, L"Paperlogy 6 SemiBold");
    HFONT font = Cached(lf);
    if (!font) { LeaveCriticalSection(&guard); return originalTextOut(dc, x, y, text, count); }
    HGDIOBJ old = SelectObject(dc, font);
    int shift = asciiGlyph ? FitAscii(dc, wide[0], lf) : (wide.size() == 1 ? SymbolOffset(dc, wide[0]) : 0);
    BOOL result = TextOutW(dc, x + shift, y, wide.data(), (int)wide.size());
    if (shift) {
        std::wstring key = wide + L":" + std::to_wstring(lf.lfHeight);
        bool seen = false;
        for (const auto& entry : loggedMetrics) if (entry == key) { seen = true; break; }
        if (!seen) {
            loggedMetrics.push_back(key);
            SIZE size{}; GetTextExtentPoint32W(dc, L"가", 1, &size);
            Log("symbol code=" + std::to_string((unsigned)wide[0]) + " font_height=" + std::to_string(lf.lfHeight) +
                " x=" + std::to_string(x) + " y=" + std::to_string(y) + " shift=" + std::to_string(shift) +
                " hangul_advance=" + std::to_string(size.cx) + "\r\n");
        }
    }
    wchar_t face[LF_FACESIZE]{}; GetTextFaceW(dc, LF_FACESIZE, face);
    Log(Utf8(std::wstring(L"draw font=") + face + L" text=" + wide) + " ok=" + std::to_string(result) + "\r\n");
    SelectObject(dc, old);
    LeaveCriticalSection(&guard);
    return result;
}
static bool Hook() {
    BYTE* image = (BYTE*)GetModuleHandleW(nullptr);
    auto dos = (IMAGE_DOS_HEADER*)image;
    auto nt = (IMAGE_NT_HEADERS*)(image + dos->e_lfanew);
    auto imports = (IMAGE_IMPORT_DESCRIPTOR*)(image + nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    unsigned installed = 0;
    for (; imports->Name; ++imports) {
        if (_stricmp((char*)image + imports->Name, "GDI32.dll") &&
            _stricmp((char*)image + imports->Name, "USER32.dll")) continue;
        auto names = (IMAGE_THUNK_DATA*)(image + imports->OriginalFirstThunk);
        auto slots = (IMAGE_THUNK_DATA*)(image + imports->FirstThunk);
        for (; names->u1.AddressOfData; ++names, ++slots) {
            if (IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal)) continue;
            auto name = (IMAGE_IMPORT_BY_NAME*)(image + names->u1.AddressOfData);
            void* replacement = nullptr;
            if (!strcmp((char*)name->Name, "TextOutA")) {
                originalTextOut = (decltype(originalTextOut))slots->u1.Function;
                replacement = (void*)KoreanTextOut;
            } else if (!strcmp((char*)name->Name, "MessageBoxA")) replacement = (void*)UnicodeMessageBox;
            else if (!strcmp((char*)name->Name, "SetWindowTextA")) replacement = (void*)UnicodeSetWindowText;
            else if (!strcmp((char*)name->Name, "SendMessageA")) {
                originalSendMessage = (decltype(originalSendMessage))slots->u1.Function;
                replacement = (void*)UnicodeSendMessage;
            }
            else if (!strcmp((char*)name->Name, "CreateWindowExA")) {
                originalCreateWindow = (decltype(originalCreateWindow))slots->u1.Function;
                replacement = (void*)UnicodeCreateWindow;
            }
            if (!replacement) continue;
            DWORD old;
            if (!VirtualProtect(&slots->u1.Function, sizeof(void*), PAGE_READWRITE, &old)) return false;
            slots->u1.Function = (ULONG_PTR)replacement;
            VirtualProtect(&slots->u1.Function, sizeof(void*), old, &old);
            ++installed;
        }
    }
    Log("installed_hooks=" + std::to_string(installed) + "\r\n");
    return installed == 5;
}
BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(module);
        InitializeCriticalSection(&guard);
        wchar_t path[32768]; GetModuleFileNameW(module, path, 32768);
        base = path; base.resize(base.find_last_of(L"\\/") + 1);
        HANDLE f = CreateFileW((base + L"hangul_map.bin").c_str(), GENERIC_READ, FILE_SHARE_READ,
                              nullptr, OPEN_EXISTING, 0, nullptr);
        if (f == INVALID_HANDLE_VALUE) return FALSE;
        DWORD bytes = GetFileSize(f, nullptr), read = 0;
        mapping.resize(bytes / 2); ReadFile(f, mapping.data(), bytes, &read, nullptr); CloseHandle(f);
        if (read != bytes || mapping.empty()) return FALSE;
        int faces = AddFontResourceExW((base + L"Paperlogy-6SemiBold.ttf").c_str(), FR_PRIVATE, nullptr);
        if (!faces) return FALSE;
        bool ok = Hook();
        Log("font_registered=" + std::to_string(faces) + " hook=" + std::to_string(ok) + "\r\n");
        return ok;
    }
    return TRUE;
}
