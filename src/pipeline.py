"""Shared patch pipeline; the packaged installer supplies already compiled runtime files."""
from pathlib import Path
import json,shutil,subprocess,sys
from paths import ROOT,SOURCE_ROOT
from pack_images import digest,pack
from patch_version import VERSION
import text_patch,dialogue_size,choice_layout

RUNTIME_FILES=['GalPapaLauncher.exe','korean_patch/GalPapaInject.exe','korean_patch/galpapa_korean.dll']

def build(game,out,original_data,prebuilt=None,status=print,progress=None):
 def notify(percent,message):
  if progress:progress(percent,message)
  else:status(message)
 notify(1,"원본 게임 검증")
 game=Path(game);out=Path(out);out.mkdir(parents=True,exist_ok=True);dist=out/'dist';(dist/'pac').mkdir(parents=True,exist_ok=True)
 expected=json.loads((SOURCE_ROOT/'original_hashes.json').read_text(encoding='utf-8'))
 archives={}
 for name in ['cgsys.ypf','cg.ypf']:
  candidate=Path(original_data)/name
  if not candidate.exists():candidate=game/'pac'/name
  if not candidate.exists() or digest(candidate)!=expected[name]:raise RuntimeError('지원하는 순정 게임 데이터가 아닙니다: '+name+' (ver1.01 원본 필요)')
  archives[name]=candidate
 for name in ['update1.ypf','ysbin.ypf']:
  if not (game/'pac'/name).exists() or digest(game/'pac'/name)!=expected[name]:raise RuntimeError('지원하는 게임 버전이 아닙니다: '+name+' (ver1.01 필요)')
 notify(3,'대사와 UI 번역 적용')
 text_patch.build(game/'pac/update1.ypf',out/'work/text',progress=lambda n,total:notify(3+18*n/total,f'스크립트 {n}/{total}'))
 notify(22,'대사창 글자 크기 적용')
 dialogue_size.build(out/'work/text/update2.ypf',out/'work/dialogue')
 choice_layout.build(out/'work/dialogue/update2.ypf',out/'work/choice')
 shutil.copyfile(out/'work/choice/update2.ypf',dist/'pac/update2.ypf')
 notify(25,'이미지 생성')
 import images
 rows=images.build(archives,out/'work',progress=lambda percent,message:notify(25+55*percent/100,message))
 notify(80,'이미지 아카이브 구성 및 검증')
 reports={}
 for name,path in archives.items():
  replacement={r['path'].replace('/','\\'):out/'work/images'/r['path'] for r in rows if r['path'].startswith(Path(name).stem+'/')}
  reports[name]=pack(path,dist/'pac'/name,replacement)
  notify(80+9*len(reports)/len(archives),name+' 구성·검증 완료')
 notify(90,'한글 런처 준비')
 if prebuilt is None:
  subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(SOURCE_ROOT/'build_native.ps1'),'-OutputDirectory',str(dist)],check=True,cwd=ROOT)
  work=out/'work/native';work.mkdir(parents=True,exist_ok=True)
  for f in (dist/'korean_patch').iterdir():
   if f.suffix.lower() in ['.obj','.exp','.lib']:f.replace(work/f.name)
 else:
  native=json.loads((Path(prebuilt)/'runtime_manifest.json').read_text(encoding='utf-8'))
  for name in RUNTIME_FILES:
   source=Path(prebuilt)/name
   if digest(source)!=native[name]:raise RuntimeError('패치 파일 내부 검증에 실패했습니다: '+name)
   destination=dist/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
 runtime=dist/'korean_patch';shutil.copyfile(out/'work/text/hangul_map.bin',runtime/'hangul_map.bin');shutil.copyfile(ROOT/'assets/fonts/Paperlogy-6SemiBold.ttf',runtime/'Paperlogy-6SemiBold.ttf')
 notify(93,'최종 파일 검증')
 files=RUNTIME_FILES+['korean_patch/hangul_map.bin','korean_patch/Paperlogy-6SemiBold.ttf','pac/update2.ypf','pac/cgsys.ypf','pac/cg.ypf']
 manifest={'files':{n:digest(dist/n) for n in files},'image_count':len(rows),'archives':reports,'inputs':{'original_archives':expected,'image_translations':{'phone_ko.json':digest(ROOT/'translation/images/phone_ko.json')},'translations':{n:digest(ROOT/'translation/reviewd'/n) for n in ['messages_ko.jsonl','ui_literals_ko.jsonl']},'fonts':{f.name:digest(f) for f in (ROOT/'assets/fonts').glob('*.ttf')}}}
 manifest['patch_version']=VERSION
 manifest['inputs']['glossary']=digest(ROOT/'translation/glossary_v1.json')
 (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 return manifest,archives
