#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <string>

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    int argc;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argc != 3) return 10;
    std::wstring game = argv[1], dll = argv[2]; LocalFree(argv);
    std::wstring command = L"\"" + game + L"\"";
    std::wstring cwd = game.substr(0, game.find_last_of(L"\\/") + 1);
    STARTUPINFOW si{sizeof(si)}; PROCESS_INFORMATION pi{};
    if (!CreateProcessW(game.c_str(), &command[0], nullptr, nullptr, FALSE, CREATE_SUSPENDED,
                        nullptr, cwd.c_str(), &si, &pi)) return 20;
    int error = 0;
    SIZE_T bytes = (dll.size() + 1) * sizeof(wchar_t);
    void* memory = VirtualAllocEx(pi.hProcess, nullptr, bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!memory || !WriteProcessMemory(pi.hProcess, memory, dll.c_str(), bytes, nullptr)) error = 21;
    HANDLE loader = nullptr;
    if (!error) {
        loader = CreateRemoteThread(pi.hProcess, nullptr, 0,
            (LPTHREAD_START_ROUTINE)GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "LoadLibraryW"), memory, 0, nullptr);
        if (!loader || WaitForSingleObject(loader, 15000) != WAIT_OBJECT_0) error = 22;
    }
    if (!error) {
        DWORD result = 0; GetExitCodeThread(loader, &result);
        if (!result) error = 23;
    }
    if (loader) CloseHandle(loader);
    if (error) {
        TerminateProcess(pi.hProcess, error);
        MessageBoxW(nullptr, L"Korean font hook could not be loaded.", L"GalPapa", MB_OK | MB_ICONERROR);
    } else {
        VirtualFreeEx(pi.hProcess, memory, 0, MEM_RELEASE);
        ResumeThread(pi.hThread);
        WaitForSingleObject(pi.hProcess, INFINITE);
        DWORD result = 0; GetExitCodeProcess(pi.hProcess, &result); error = (int)result;
    }
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    return error;
}
