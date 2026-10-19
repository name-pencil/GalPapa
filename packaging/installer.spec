# PyInstaller bundle: source rules/data/fonts and precompiled runtime only.
from pathlib import Path
import os
project=Path(SPECPATH).parent
native=Path(os.environ['GALPAPA_BUILD_NATIVE'])
patch_version=(project/'VERSION').read_text(encoding='ascii').strip()
datas=[(str(p),'assets/fonts') for p in (project/'assets/fonts').glob('*.ttf')]
datas.append((str(project/'VERSION'),'.'))
datas.append((str(project/'LICENSE'),'licenses'))
datas.append((str(project/'LICENSES/GARbro.txt'),'licenses'))
for name in ['image_specs.json','original_hashes.json','restaurant_backgrounds.json']:
 datas.append((str(project/'src'/name),'src'))
for name in ['messages_ko.jsonl','ui_literals_ko.jsonl','voice_text_ko.jsonl']:
 datas.append((str(project/'translation/reviewd'/name),'translation/reviewd'))
datas.append((str(project/'translation/images/phone_ko.json'),'translation/images'))
datas.append((str(project/'translation/glossary_v1.json'),'translation'))
datas.append((str(native/'runtime_manifest.json'),'prebuilt'))
for relative in ['GalPapaLauncher.exe','korean_patch/GalPapaInject.exe','korean_patch/galpapa_korean.dll']:
 f=Path(relative);datas.append((str(native/f),str(Path('prebuilt')/f.parent)))
a=Analysis([str(project/'src/installer.py')],pathex=[str(project/'src')],binaries=[],datas=datas,hiddenimports=[],hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['tkinter','_tkinter','IPython','notebook','matplotlib','pandas','scipy','pytest','PyQt5','PyQt6','PySide6'],noarchive=False,optimize=0)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='GalPapaKoreanPatch-v'+patch_version,version=os.environ['GALPAPA_VERSION_INFO'],debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=True,disable_windowed_traceback=False,uac_admin=False)
