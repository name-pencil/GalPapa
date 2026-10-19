"""Generate all translated images solely from original archives, source rules and fonts."""
from pathlib import Path
import json,hashlib,re,shutil,zlib
import numpy as np
from PIL import Image,ImageFont
import config_images as config
import base_images as base
import popup_text as popup
import app_ui_text as app
import image_effects as final
import cards
from archive_index import index,safe_relative
from paths import ROOT, SOURCE_ROOT
SPECS=json.loads((SOURCE_ROOT/'image_specs.json').read_text(encoding='utf-8'))
DEEP={21,23,26,29,30,33,37,41,45,73,74,76,77,79,80,84,88,90,91,92,94,96,98,100,104,108,110,111,113,114,116,117,190,191}
TITLE={49,52,55,57,59,61,64,66,68}
BG_PATHS={v['path'] for v in json.loads((SOURCE_ROOT/'restaurant_backgrounds.json').read_text(encoding='utf-8')).values()}

def export_originals(archives,out):
 for name in ['cgsys.ypf','cg.ypf']:
  with archives[name].open('rb') as stream:
   for e in index(archives[name]):
    if name=='cg.ypf' and e['name']!='cg\\bg\\caution.png' and not e['name'].startswith('cg\\phone\\') and not e['name'].startswith('cg\\pop\\') and e['name'].replace('\\','/') not in BG_PATHS:continue
    if not e['name'].lower().endswith('.png'):continue
    stream.seek(e['offset']);data=stream.read(e['packed'])
    if e['compressed']:data=zlib.decompress(data)
    dest=out/safe_relative(e['name']);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
 for spec in SPECS:
  assert hashlib.sha256((out/spec['path']).read_bytes()).hexdigest()==spec['original_sha256'],spec['path']

def headings(original,before,key):
 after=before.copy();rects=[]
 for spec in popup.POPUPS[key]:
  if not spec['glow']:continue
  x0,y0,x1,y1=spec['rect'];size=spec['size'];text=spec['text']
  while ImageFont.truetype(str(final.FONT),size*4).getlength(text)/4>x1-x0-8:size-=1
  clean=popup.erase_text(original,spec['rect'],True)
  cx=(x0+x1)/2
  if spec['align']=='left':cx=x0+ImageFont.truetype(str(final.FONT),size).getlength(text)/2
  mask=final.mask_text(original.size,text,size,(cx,(y0+y1)/2))
  rect=(max(0,x0-14),max(0,y0-14),min(original.width,x1+14),min(original.height,y1+14))
  after=final.clip_region(after,final.paste_effect(clean,mask,'popup'),rect);rects.append(rect)
 return after,rects

def build(archives,out,progress=None):
 reporter=progress or (lambda percent,message:None)
 notify=lambda percent,message:reporter(percent*.45,message)
 notify(0,"원본 이미지 추출")
 out=Path(out);source=out/'original_images';source.mkdir(parents=True,exist_ok=True)
 export_originals(archives,source)
 stage=out/'base_images';(stage/'images').mkdir(parents=True,exist_ok=True)
 config.SOURCE=source/'cgsys/config';config.OUT=stage/'config';(config.OUT/'images').mkdir(parents=True,exist_ok=True)
 notify(10,"환경 설정 이미지 생성")
 config_records=config.build_images()
 base.SOURCE=source/'cgsys';base.OUT=stage;popup.SOURCE=source;app.SOURCE=source/'cgsys';final.SRC=source
 base_count=[0]
 def base_progress(relative):
  base_count[0]+=1
  notify(20+45*base_count[0]/156,f'기본 이미지 {base_count[0]}/156')
 base.PROGRESS_CALLBACK=base_progress
 try:base.make_images()
 finally:base.PROGRESS_CALLBACK=None
 target=out/'images';target.mkdir(exist_ok=True);cache={};report=[];layer=cards.label_layer()
 for spec in SPECS:
  i=spec['id'];path=spec['path'];rel=path.removeprefix('cgsys/');text=spec['text'];size=spec['font_size']
  original=Image.open(source/path).convert('RGBA')
  if i<=47:before=Image.open(config.OUT/'images'/Path(path).name).convert('RGBA')
  else:before=Image.open(stage/('caution.png' if i==204 else 'images/'+rel)).convert('RGBA')
  after=before;rects=None
  final.BASELINE_ALIGNMENT=spec['baseline_alignment']
  # Same original pixels/text/style share the actual render, not just a filename.
  key=(hashlib.sha256(original.tobytes()).hexdigest(),text,size,spec['baseline_alignment'], 'base' if i not in DEEP|TITLE and not 69<=i<=71 and not 118<=i<=194 else ('deep' if i in DEEP else 'title' if i in TITLE else 'card' if 145<=i<=180 else i))
  reused=cache.get(key)
  if reused:after=reused[1].copy()
  elif i in DEEP:after,rect=final.button(original,text,size);rects=[rect]
  elif i in TITLE:after,rect=final.title(original,text,size);rects=[rect]
  elif 69<=i<=71:after,rect=final.button(original,text,18,'off' if i==69 else 'deep');rects=[rect]
  elif 118<=i<=136:after,rect=final.dialog(original,text);rects=[rect]
  elif 137<=i<=144:after,rects=headings(original,before,Path(path).stem.removeprefix('dialog_'))
  elif 145<=i<=180:
   donor=re.sub(r'(koh|mio|yui)0([123])_',r'\g<1>9\2_',path)
   after=cards.render(original,Image.open(source/donor).convert('RGBA'),layer)
  elif 185<=i<=188:after,rect=final.button(original,text,18,'outline' if i<=186 else 'deep',59 if i==185 else 69);rects=[rect]
  elif 192<=i<=194:after,rects=final.customization(original)
  elif i==204:after,rects=final.caution(original,before)
  if rects and i!=204:
   allowed=np.zeros((original.height,original.width),bool)
   for x0,y0,x1,y1 in rects:allowed[y0:y1,x0:x1]=True
   reference=before if 137<=i<=144 else original
   assert np.array_equal(np.array(after)[~allowed],np.array(reference)[~allowed]),i
  if not reused:cache[key]=(i,after.copy())
  dest=target/path;dest.parent.mkdir(parents=True,exist_ok=True);after.save(dest)
  notify(65+35*(len(report)+1)/len(SPECS),f'공통 이미지 {len(report)+1}/{len(SPECS)}')
  report.append({**spec,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'reused_from':reused[0] if reused else None})
 import restaurant_images,phone_images
 menu_rows=restaurant_images.build(source,target,len(report)+1,progress=lambda n:reporter(45+25*min(n/378,1),f'식당 이미지 {n}/378'))
 extra_rows=[r for r in menu_rows if r['path'].endswith('/restaurant_back04.png')]
 report.extend(r for r in menu_rows if r not in extra_rows)
 phone_rows=phone_images.build(source,target,len(report)+1,progress=lambda n,total:reporter(70+30*n/total,f'휴대폰 이미지 {n}/{total}'))
 report.extend(phone_rows)
 for extra in extra_rows:
  extra['id']=len(report)+1;report.append(extra)
 import scene_ui_images
 report.extend(scene_ui_images.build(source,target,len(report)+1))
 import result_ui_images
 report.extend(result_ui_images.build(source,target,len(report)+1))
 import job_popup_images
 report.extend(job_popup_images.build(source,target,len(report)+1))
 import job_button_images
 report.extend(job_button_images.build(source,target,len(report)+1))
 import week_images
 report.extend(week_images.build(source,target,len(report)+1))
 import endless_images
 report.extend(endless_images.build(source,target,len(report)+1))
 reporter(100,f'이미지 {len(report)}개 완료')
 (out/'image_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 return report
