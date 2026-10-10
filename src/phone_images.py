"""Image-only phone translations; retain bubble borders, avatars and timestamps."""
import json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from paths import ROOT
FONT=ROOT/'assets/fonts/Paperlogy-5Medium.ttf'

def wrap(text,font,width,words=True):
 lines=[]
 for paragraph in text.split('\n'):
  line=''
  units=paragraph.split(' ') if words else list(paragraph)
  for unit in units:
   candidate=(line+' '+unit) if words and line else line+unit
   if line and font.getlength(candidate)>width:lines.append(line.rstrip());line=unit.lstrip()
   else:line=candidate
   if font.getlength(line)>width:
    fragments=wrap(line,font,width,False);lines.extend(fragments[:-1]);line=fragments[-1]
  if line:lines.append(line.rstrip())
 return lines

def render(original,spec):
 from phone_bubbles import render as fitted
 return fitted(original,spec)


def build(source,target,start_id=205,progress=None):
 specs=json.loads((ROOT/'translation/images/phone_ko.json').read_text(encoding='utf-8'));rows=[];cache={}
 for n,s in enumerate(specs):
  p=source/s['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==s['source_sha256']
  im=Image.open(p).convert('RGBA');cache_key=(s['source_sha256'],s['text']);reused=cache.get(cache_key)
  if reused:
   out=Image.open(reused[1]).convert('RGBA')
  else:
   out=render(im,s)
  dest=target/s['path'];dest.parent.mkdir(parents=True,exist_ok=True);out.save(dest)
  if not reused:cache[cache_key]=(start_id+n,dest)
  rows.append({'id':start_id+n,'path':s['path'],'text':s['text'],'font_size':12,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'reused_from':reused[0] if reused else None})
  if progress:progress(n+1,len(specs)+5)
 # Phone shells: preserve English MIO and the original heart icon.
 from restaurant_images import draw
 for name,rect,text in [('phone_app_koh.png',(217,75,322,105),'코하룬'),('phone_app_mio.png',None,None),('phone_app_yui.png',(251,77,269,101),'유'),('phone_line_koh.png',(126,74,227,105),'코하루'),('phone_line_mio.png',None,None),('phone_line_yui.png',(126,74,227,105),'유이나')]:
  rel='cg/phone/'+name;im=Image.open(source/rel).convert('RGBA');textlist=[]
  if rect:
   x0,y0,x1,y1=rect;a=np.array(im)
   for y in range(y0,y1):a[y,x0:x1]=a[y,210 if 'app_' in name else 231]
   im=draw(Image.fromarray(a),rect,text,16,(65,65,65,255),left=130 if 'line_' in name else None);textlist.append(text)
  if 'app_' in name:
   rect=(220,678,332,697);im.paste((247,247,247,255),rect);im=draw(im,rect,'메시지 입력',10,(178,178,178,255),left=224);textlist.append('메시지 입력')
  if not textlist:continue
  dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);im.save(dest)
  rows.append({'id':start_id+len(rows),'path':rel,'text':' / '.join(textlist),'font_size':16,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'reused_from':None})
  if progress:progress(len(rows),len(specs)+5)
 return rows
