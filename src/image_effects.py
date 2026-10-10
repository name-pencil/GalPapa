from pathlib import Path
import collections
import numpy as np
from PIL import Image,ImageFont,ImageFilter
import effects
from popup_text import lettering,CAUTION
FONT=effects.FONT
SRC=None
BASELINE_ALIGNMENT=False

def mask_text(*args,**kwargs):
 kwargs['baseline_alignment']=BASELINE_ALIGNMENT
 return effects.mask_text(*args,**kwargs)

def paste_effect(clean,m,kind):
 a=np.array(clean).astype(float)
 if kind=='deep':
  a=effects.blend_color(a,(216,91,149,248),effects.grow(m,3).filter(ImageFilter.GaussianBlur(1)))
 elif kind=='popup':
  target=a.copy();target[:,:,:3]=np.minimum(255,target[:,:,:3]+[38,36,29]);t=np.array(effects.grow(m,5).filter(ImageFilter.GaussianBlur(.9)))[...,None]/255
  a=a*(1-t)+target*t;a=effects.blend_color(a,(48,7,40,255),effects.grow(m,3))
 elif kind=='outline':
  a=effects.blend_color(a,(42,5,33,255),effects.grow(m,1))
 elif kind=='off':
  a=effects.blend_color(a,(160,110,147,205),effects.grow(m,2).filter(ImageFilter.GaussianBlur(.8)))
  a=effects.blend_color(a,(14,0,9,219),effects.grow(m,1))
 a=effects.blend_color(a,(255,255,255,255),m)
 return Image.fromarray(np.uint8(np.clip(np.rint(a),0,255)))

def clip_region(src,new,rect):
 out=src.copy();out.paste(new.crop(rect),rect[:2]);return out

def button(src,text,px,kind='deep',left_limit=None):
 a=np.array(src);w,h=src.size
 white=(a[:,:,:3].min(2)>200)&(a[:,:,3]>170)
 white[:5]=False;white[h-5:]=False;white[:,:12]=False;white[:,w-12:]=False
 if left_limit: white[:,:left_limit]=False
 yy,xx=np.where(white);assert len(xx)
 cy=(int(yy.min())+int(yy.max())+1)/2
 cx=(left_limit+4+ImageFont.truetype(str(FONT),px).getlength(text)/2) if left_limit else w/2
 m=mask_text(src.size,text,px,(cx,cy))
 mb=m.getbbox();x0=max(left_limit or 12,min(int(xx.min()),mb[0])-8);x1=min(w-10,max(int(xx.max())+1,mb[2])+8)
 y0=max(5,min(int(yy.min()),mb[1])-7);y1=min(h-5,max(int(yy.max())+1,mb[3])+7)
 rect=(x0,y0,x1,y1);clean=a.copy()
 color=collections.Counter(map(tuple,a.reshape(-1,4))).most_common(1)[0][0]
 clean[y0:y1,x0:x1]=color
 out=clip_region(src,paste_effect(Image.fromarray(clean),m,kind),rect)
 return out,rect

def title(src,text,px):
 a=np.array(src);rect=(38,5,338,61);clean=a.copy()
 for y in range(5,61):clean[y,38:338]=a[y,25]
 center=(53+ImageFont.truetype(str(effects.MAPLE),px).getlength(text)/2,33)
 m=mask_text(src.size,text,px,center,effects.MAPLE)
 v=effects.blend_color(clean.astype(float),(255,96,167,228),effects.grow(m,5).filter(ImageFilter.GaussianBlur(1)))
 v=effects.blend_color(v,(255,255,255,255),effects.grow(m,2));v=effects.blend_color(v,(255,95,146,255),m)
 return clip_region(src,Image.fromarray(np.uint8(np.clip(np.rint(v),0,255))),rect),rect

def dialog(src,text):
 a=np.array(src);w,h=src.size;rect=(45,30,w-45,114);clean=a.copy()
 reference=np.array(Image.open(SRC/'cgsys/confirm/dialog_save.png').convert('RGBA'))
 for x in range(rect[0],rect[2]):clean[30:114,x]=reference[30:114,x%151]
 mask=Image.new('L',src.size);lines=text.splitlines()
 for j,line in enumerate(lines):
  m=mask_text(src.size,line,25,(w/2,72+(j-(len(lines)-1)/2)*32),tracking=.7,align_closing_quotes=True)
  mask=Image.fromarray(np.maximum(np.array(mask),np.array(m)))
 return clip_region(src,paste_effect(Image.fromarray(clean),mask,'popup'),rect),rect

def customization(src):
 a=np.array(src);clean=a.copy();rect=(440,20,750,78)
 for x in range(440,750):clean[20:78,x]=a[20:78,x%151+151]
 m=mask_text(src.size,'색상 설정',27,(570,48))
 result=clip_region(src,paste_effect(Image.fromarray(clean),m,'popup'),rect)
 rects=[rect]
 for rect,text in [((372,143,436,184),'머리'),((372,212,436,254),'피부'),((372,281,436,324),'속옷')]:
  x0,y0,x1,y1=rect;clean=np.array(result)
  # Flat panel opacity and original diamond pattern are shared 151px apart.
  for x in range(x0,x1):clean[y0:y1,x]=a[y0:y1,x+151]
  bg=Image.fromarray(clean);ink=lettering(src.size,[text],font_size=18,center=(None,(y0+y1)/2),left=376,glow=False,outline=2)
  result=clip_region(result,Image.alpha_composite(bg,ink),rect);rects.append(rect)
 assert np.array_equal(np.array(result)[140:326,350:372],a[140:326,350:372])
 return result,rects

def caution(src,before):
 a=np.array(src);clean=np.array(before);rects=[(300,469,980,506),(300,517,980,602)]
 for l,t,r,b in rects:
  for y in range(t,b):
   f=(y-t+1)/(b-t+1);clean[y,l:r]=np.rint(a[t-1,l:r].astype(float)*(1-f)+a[b,l:r].astype(float)*f).astype('uint8')
 result=Image.fromarray(clean)
 for rect,text,px in CAUTION[5:]:
  x0,y0,x1,y1=rect;result.alpha_composite(lettering(src.size,[text],font_size=px,center=(640,(y0+y1)/2),glow=False,outline=0))
 assert np.array_equal(np.array(result)[417:449],a[417:449]);assert np.array_equal(np.array(result)[:210],a[:210])
 return result,rects
