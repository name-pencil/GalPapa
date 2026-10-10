// Standalone Windows launcher: no .NET or separately installed VC runtime.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
namespace fs = std::filesystem;
static std::wstring quote(const fs::path& path) { return L"\"" + path.wstring() + L"\""; }
static void log(const fs::path& root, const char* text) {
#ifdef GALPAPA_DIAGNOSTICS
    std::ofstream stream(root / L"launcher.log", std::ios::app); stream << text << "\n";
#endif
}
int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR args, int) {
    wchar_t self[32768]; GetModuleFileNameW(nullptr, self, 32768);
    fs::path root = fs::path(self).parent_path(), game;
    bool check = std::wstring(args).find(L"--check") != std::wstring::npos;
    std::wstring drive, target;
    HANDLE mutex = nullptr;
    try {
        // Prefer a game beside the launcher; do not search backups/trash recursively.
        if (fs::exists(root / L"galpapa.exe")) game = root;
        else {
            std::vector<fs::path> matches;
            for (auto& entry : fs::directory_iterator(root))
                if (entry.is_directory() && fs::exists(entry.path() / L"galpapa.exe") && fs::is_directory(entry.path() / L"pac")) matches.push_back(entry.path());
            if (matches.size() != 1) throw std::runtime_error("game path");
            game = matches.front();
        }
        target = L"\\??\\" + game.wstring();
        mutex = CreateMutexW(nullptr, FALSE, L"Local\\GalPapaDriveAllocation");
        if (!mutex) throw std::runtime_error("mutex");
        DWORD wait = WaitForSingleObject(mutex, 30000);
        if (wait != WAIT_OBJECT_0 && wait != WAIT_ABANDONED) throw std::runtime_error("mutex wait");
        for (wchar_t letter = L'Z'; letter >= L'D'; --letter) {
            wchar_t candidate[] = {letter, L':', 0}; wchar_t existing[32768];
            if (QueryDosDeviceW(candidate, existing, 32768) || GetLastError() != ERROR_FILE_NOT_FOUND) continue;
            if (DefineDosDeviceW(DDD_RAW_TARGET_PATH, candidate, target.c_str())) { drive = candidate; break; }
        }
        ReleaseMutex(mutex); CloseHandle(mutex); mutex = nullptr;
        if (drive.empty()) throw std::runtime_error("drive mapping");
        std::wstring cwd = drive + L"\\", exe = cwd + L"galpapa.exe";
        if (!fs::exists(exe) || !fs::is_directory(cwd + L"pac")) throw std::runtime_error("mapped path");
        if (check) log(root, "CHECK OK: game path mapping accessible.");
        else {
            fs::path runtime = root / L"korean_patch", injector = runtime / L"GalPapaInject.exe", dll = runtime / L"galpapa_korean.dll";
            if (!fs::exists(injector) || !fs::exists(dll) || !fs::exists(runtime / L"hangul_map.bin") || !fs::exists(runtime / L"Paperlogy-6SemiBold.ttf")) throw std::runtime_error("runtime missing");
            std::wstring command = quote(injector) + L" " + quote(fs::path(exe)) + L" " + quote(dll);
            STARTUPINFOW si{}; si.cb = sizeof(si); PROCESS_INFORMATION pi{};
            if (!CreateProcessW(injector.c_str(), command.data(), nullptr, nullptr, FALSE, 0, nullptr, cwd.c_str(), &si, &pi)) throw std::runtime_error("launch");
            CloseHandle(pi.hThread); WaitForSingleObject(pi.hProcess, INFINITE); CloseHandle(pi.hProcess);
            log(root, "Game process exited.");
        }
        if (!DefineDosDeviceW(DDD_REMOVE_DEFINITION | DDD_EXACT_MATCH_ON_REMOVE | DDD_RAW_TARGET_PATH, drive.c_str(), target.c_str())) throw std::runtime_error("mapping cleanup");
        log(root, "Mapping cleanup OK."); return 0;
    } catch (...) {
        if (mutex) { ReleaseMutex(mutex); CloseHandle(mutex); }
        if (!drive.empty()) DefineDosDeviceW(DDD_REMOVE_DEFINITION | DDD_EXACT_MATCH_ON_REMOVE | DDD_RAW_TARGET_PATH, drive.c_str(), target.c_str());
        log(root, "Launcher failed.");
        if (!check) MessageBoxW(nullptr, L"게임 실행에 실패했습니다. 게임 폴더와 korean_patch 파일을 확인해 주세요.", L"GalPapa 한글 런처", MB_OK | MB_ICONERROR);
        return 1;
    }
}
