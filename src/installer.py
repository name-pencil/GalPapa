"""Offline single-file installer. All Python/native dependencies are bundled."""
from pathlib import Path
import sys,os,json,hashlib,shutil,tempfile,traceback,argparse,time
import re
from paths import ROOT
from pack_images import digest
from pipeline import build,RUNTIME_FILES
from install import install,running_for_game
from patch_version import VERSION

TITLE='GalPapa 한글 패치 v'+VERSION

def self_test():
 import cv2,numpy,PIL,psutil
 from PIL import ImageFont
 for f in (ROOT/'assets/fonts').glob('*.ttf'):ImageFont.truetype(str(f),20)
 from effects import SYMBOL
 ImageFont.truetype(str(SYMBOL),20)
 expected=json.loads((ROOT/'prebuilt/runtime_manifest.json').read_text(encoding='utf-8'))
 for name in RUNTIME_FILES:assert digest(ROOT/'prebuilt'/name)==expected[name]
 for name in ['messages_ko.jsonl','ui_literals_ko.jsonl','voice_text_ko.jsonl']:assert (ROOT/'translation/reviewd'/name).is_file()
 return {'ok':True,'version':VERSION,'frozen':bool(getattr(sys,'frozen',False)),'python':sys.version.split()[0],'native_files':len(expected),'network_required':False}

def patch(game,status):
 game=Path(game).resolve()
 if not (game/'galpapa.exe').is_file() or not (game/'pac').is_dir():raise RuntimeError('패치 EXE를 galpapa.exe와 pac 폴더가 있는 게임 폴더에 넣고 실행해 주세요.')
 import psutil
 if running_for_game(game):raise RuntimeError('실행 중인 게임과 런처를 종료한 뒤 다시 실행해 주세요.')
 meta=game/'.galpapa_korean';meta.mkdir(exist_ok=True);originals=meta/'originals';originals.mkdir(exist_ok=True)
 # Original archives and rollback copies are intentionally persistent.
 required=sum((game/'pac'/n).stat().st_size for n in ['cgsys.ypf','cg.ypf'])*4+300*1024*1024
 if shutil.disk_usage(game).free<required:raise RuntimeError('패치와 원본 백업을 위한 여유 공간이 부족합니다. 약 '+str((required+1024**3-1)//1024**3)+' GB가 필요합니다.')
 def update(percent,message):
  status(percent,message)
 # Workspace on the game volume: no dependency on user-installed interpreters.
 with tempfile.TemporaryDirectory(prefix='work-',dir=meta) as folder:
  work=Path(folder)
  manifest,archives=build(game,work,originals,ROOT/'prebuilt',progress=update)
  update(95,'원본 백업')
  copied=0
  total=sum(path.stat().st_size for name,path in archives.items() if not (originals/name).exists())
  for name,path in archives.items():
   dest=originals/name
   if not dest.exists():
    temp=dest.with_suffix('.copying')
    with path.open('rb') as src,temp.open('wb') as dst:
     for chunk in iter(lambda:src.read(4*1024*1024),b''):
      dst.write(chunk);copied+=len(chunk);update(95+2*copied/max(total,1),f'원본 백업 {copied//1048576}/{total//1048576} MB')
     dst.flush();os.fsync(dst.fileno())
    if digest(temp)!=manifest['inputs']['original_archives'][name]:raise RuntimeError('원본 백업 검증 실패: '+name)
    os.replace(temp,dest)
  update(97,'패치 파일 설치 준비·검증')
  report=install(game,game,work/'dist',manifest,meta,progress=lambda n,total,name:update(97+2*n/total,f'설치 {n}/{total}: {Path(name).name}'))
  (meta/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 update(100,'완료: GalPapaLauncher.exe로 실행하세요.')
 return {'ok':True,'game':str(game),'launcher':str(game/'GalPapaLauncher.exe'),'files':manifest['files'],'installation':report}

class ConsoleProgress:
 def __init__(self):
  self.start=time.monotonic();self.last=-1;self.tick=0;self.tty=False
  if sys.stdout:
   try:sys.stdout.reconfigure(encoding='utf-8',errors='replace')
   except (AttributeError,ValueError):pass
   if sys.stdout.isatty():
    try:
     import ctypes
     k=ctypes.windll.kernel32;k.SetConsoleTitleW(TITLE);mode=ctypes.c_uint();handle=k.GetStdHandle(-11)
     self.tty=bool(k.GetConsoleMode(handle,ctypes.byref(mode)) and k.SetConsoleMode(handle,mode.value|4))
    except Exception:pass
 def __call__(self,percent,message):
  value=max(self.last,min(100,int(percent)));now=time.monotonic()
  milestone=any(a==b for a,b in re.findall(r'(\d+)/(\d+)',message)) or message.endswith('완료')
  if value==self.last and not milestone and (not self.tty or now-self.tick<.25):return
  self.last=value;self.tick=now;elapsed=int(now-self.start)
  bar='#'*(value//5)+'-'*(20-value//5)
  line=f'[{bar}] {value:3d}%  {elapsed//60:02d}:{elapsed%60:02d}  {message}'
  print(('\r\x1b[2K' if self.tty else '')+line,end='' if self.tty and value<100 else '\n',flush=True)
 def finish(self):
  if self.tty and self.last<100:print()

def main():
 p=argparse.ArgumentParser(description='GalPapa 콘솔 한글 패치')
 p.add_argument('--version',action='version',version=TITLE)
 p.add_argument('--game',type=Path);p.add_argument('--headless',action='store_true',help='완료 후 입력 대기 생략')
 p.add_argument('--no-pause',action='store_true');p.add_argument('--self-test',action='store_true');p.add_argument('--report',type=Path)
 a=p.parse_args();game=a.game or (Path(sys.executable).parent if getattr(sys,'frozen',False) else Path.cwd())
 progress=ConsoleProgress()
 if not a.self_test:
  print(TITLE+'\n게임 폴더: '+str(game)+'\n진행률은 단계별 처리량 기준입니다. 패치가 끝날 때까지 창을 닫지 마세요.\n',flush=True)
 try:
  result=self_test() if a.self_test else patch(game,progress);code=0
  if a.self_test:print('내장 실행 환경 검사 완료.',flush=True)
 except BaseException as error:
  progress.finish();result={'ok':False,'error':traceback.format_exc()};code=130 if isinstance(error,KeyboardInterrupt) else 1
  print('\n중단되었습니다.' if code==130 else '\n패치를 완료하지 못했습니다: '+str(error),flush=True)
  try:
   log=Path(game)/'.galpapa_korean/error.log'
   if log.parent.is_dir():log.write_text(result['error'],encoding='utf-8')
  except OSError:pass
 if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 if not (a.self_test or a.headless or a.no_pause) and sys.stdin and sys.stdin.isatty():
  try:input('\nEnter를 누르면 닫힙니다.')
  except (EOFError,KeyboardInterrupt):pass
 return code
if __name__=='__main__':sys.exit(main())
