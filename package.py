"""Build one versioned patch EXE without original game data or persistent caches."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from patch_version import VERSION

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'build/release')
    options = parser.parse_args()
    if sys.platform != 'win32' or sys.maxsize <= 2**32:
        raise RuntimeError('Build with 64-bit Python on Windows.')
    if os.environ.get('GITHUB_REF_TYPE') == 'tag' and os.environ.get('GITHUB_REF_NAME') != 'v' + VERSION:
        raise ValueError('Release tag must match VERSION: v' + VERSION)
    parts = tuple(map(int, VERSION.split('.'))) + (0,)
    if max(parts) > 65535: raise ValueError('Windows version components must be <= 65535')
    filename = 'GalPapaKoreanPatch-v' + VERSION
    destination = options.out.resolve()
    with tempfile.TemporaryDirectory(prefix='galpapa-package-') as folder:
        work = Path(folder); native = work / 'native'
        subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                        str(ROOT/'src/build_native.ps1'), '-OutputDirectory', str(native)], check=True, cwd=ROOT)
        files = ['GalPapaLauncher.exe', 'korean_patch/GalPapaInject.exe', 'korean_patch/galpapa_korean.dll']
        hashes = {n: hashlib.sha256((native/n).read_bytes()).hexdigest() for n in files}
        (native/'runtime_manifest.json').write_text(json.dumps(hashes), encoding='utf-8')
        version_file = work/'version_info.txt'
        version_file.write_text(
            f"VSVersionInfo(ffi=FixedFileInfo(filevers={parts!r},prodvers={parts!r},"
            "mask=0x3f,flags=0x0,OS=0x40004,fileType=0x1,subtype=0x0,date=(0,0)),"
            "kids=[StringFileInfo([StringTable('040904B0',["
            "StringStruct('FileDescription','GalPapa Korean Patch'),"
            f"StringStruct('FileVersion','{VERSION}'),StringStruct('ProductVersion','{VERSION}'),"
            f"StringStruct('OriginalFilename','{filename}.exe'),"
            "StringStruct('ProductName','GalPapa Korean Patch')])]),"
            "VarFileInfo([VarStruct('Translation',[1033,1200])])])", encoding='utf-8')
        env = dict(os.environ, GALPAPA_BUILD_NATIVE=str(native), GALPAPA_VERSION_INFO=str(version_file))
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                        '--distpath', str(work/'dist'), '--workpath', str(work/'pyinstaller'),
                        str(ROOT/'packaging/installer.spec')], check=True, cwd=ROOT, env=env)
        exe = work/'dist'/(filename+'.exe')
        from PyInstaller.archive.readers import CArchiveReader
        for name in CArchiveReader(str(exe)).toc:
            path = name.replace('\\','/').lower()
            if path.endswith(('.ypf','.sav','.png','.jpg','.log')) or any(
                    part in path.split('/') for part in ('trash','original_game_data','tests')):
                raise RuntimeError('Unexpected asset in EXE: '+name)
        subprocess.run([str(exe),'--self-test','--no-pause'], check=True)
        destination.mkdir(parents=True, exist_ok=True)
        target = destination/exe.name
        shutil.copyfile(exe,target)
    print('Single-file patch: '+str(target))

if __name__ == '__main__': main()
