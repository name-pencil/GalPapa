"""Install a matched launcher/runtime/archive set after verifying every staged file."""
import json,os,shutil,datetime
from pathlib import Path
import psutil
from pack_images import digest

def running_for_game(game,root=None):
 game=Path(game).resolve();root=Path(root or game).resolve()
 targets={game/'galpapa.exe',game/'GalPapaLauncher.exe',game/'korean_patch/GalPapaInject.exe',root/'GalPapaLauncher.exe',root/'korean_patch/GalPapaInject.exe'}
 names={'galpapa.exe','galpapalauncher.exe','galpapainject.exe'};running=[]
 for process in psutil.process_iter(['pid','name','exe']):
  if (process.info['name'] or '').lower() not in names:continue
  executable=process.info.get('exe')
  # Unreadable process paths cannot safely be ruled out.
  if executable is None or Path(executable).resolve() in targets:running.append(process.info)
 return running

def backup_shared_save(game,out):
 """Keep a verified copy of shared state; never rewrite the live save."""
 source=Path(game)/'save/gsd.sd'
 if not source.is_file():return None
 expected=digest(source)
 folder=Path(out)/'save_backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
 folder.mkdir(parents=True,exist_ok=False)
 target=folder/'gsd.sd'
 with source.open('rb') as inp,target.open('xb') as stream:
  shutil.copyfileobj(inp,stream,1024*1024);stream.flush();os.fsync(stream.fileno())
 if digest(target)!=expected or digest(source)!=expected:
  raise RuntimeError('공통 저장 데이터 백업 검증 실패: 게임을 종료한 뒤 다시 시도해 주세요.')
 (folder/'manifest.json').write_text(json.dumps({'source':str(source.resolve()),'sha256':expected},indent=2),encoding='utf-8')
 return str(target.resolve())

def install(root,game,dist,manifest,out,progress=None):
 running=running_for_game(game,root)
 if running:raise RuntimeError('Close the game before installation: '+str(running))
 stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup=out/'install_backups'/stamp
 mapping={}
 for relative,expected in manifest['files'].items():
  source=dist/relative
  if digest(source)!=expected:raise RuntimeError('Staged file changed: '+relative)
  dest=game/'pac'/Path(relative).name if relative.startswith('pac/') else root/relative
  mapping[relative]=(source,dest,expected)
 prepared=[];done=[];records=[];save_backup=None
 try:
  # Finish durable copies before changing any live file.
  for rel,(source,dest,expected) in mapping.items():
   if dest.exists() and digest(dest)==expected:
    records.append({'file':rel,'action':'already_matches','sha256':expected});continue
   dest.parent.mkdir(parents=True,exist_ok=True);temp=dest.with_name(dest.name+'.installing-'+stamp)
   prepared.append((rel,dest,temp,expected))
   with source.open('rb') as inp,temp.open('xb') as target:
    shutil.copyfileobj(inp,target,1024*1024);target.flush();os.fsync(target.fileno())
   assert digest(temp)==expected
  if prepared:
   # Back up shared state before the first live file replacement. A failure
   # aborts installation; the original gsd.sd remains untouched.
   save_backup=backup_shared_save(game,out)
  for number,(rel,dest,temp,expected) in enumerate(prepared,1):
   saved=backup/rel
   if dest.exists():saved.parent.mkdir(parents=True,exist_ok=True);os.replace(dest,saved)
   else:saved=None
   done.append((dest,saved));os.replace(temp,dest);assert digest(dest)==expected
   records.append({'file':rel,'action':'replaced','sha256':expected,'backup':str(saved) if saved else None})
   if progress:progress(number,len(prepared),rel)
 except BaseException:
  for dest,saved in reversed(done):
   if saved is not None:os.replace(saved,dest)
   elif dest.exists():dest.unlink()
  raise
 finally:
  for _,_,temp,_ in prepared:temp.unlink(missing_ok=True)
 report={'time':stamp,'method':'verify all, fsync, replace with rollback','files':records,'shared_save_backup':save_backup}
 (out/'install_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 return report
