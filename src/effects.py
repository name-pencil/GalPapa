from pathlib import Path
import numpy as np
import cv2
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import os
from paths import ROOT, SOURCE_ROOT
FONT=ROOT/"assets/fonts/Paperlogy-6SemiBold.ttf"
MAPLE=ROOT/"assets/fonts/Maplestory Bold.ttf"
SYMBOL=Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts/seguisym.ttf"
# Keep the reviewed appearance on standard Windows installations. The bundled
# MapleStory font supplies the same heart character when this OS font is absent.
if not SYMBOL.is_file():SYMBOL=MAPLE
def mask_text(size,text,px,center,font=FONT,tracking=0,baseline_alignment=False,align_closing_quotes=False):
 s=4; mask=Image.new('L',(size[0]*s,size[1]*s)); d=ImageDraw.Draw(mask)
 base_font=ImageFont.truetype(str(font),px*s)
 # Match visible ink height, since equal font sizes give a smaller symbol.
 ref=base_font.getbbox('유'); target_height=ref[3]-ref[1]
 heart_font=ImageFont.truetype(str(SYMBOL),px*s)
 if '♥' in text:
  candidates=[ImageFont.truetype(str(SYMBOL),n) for n in range(px*s,px*s*2+1)]
  heart_font=min(candidates,key=lambda f:abs((f.getbbox('♥')[3]-f.getbbox('♥')[1])-target_height))
 fonts=[heart_font if c=='♥' else base_font for c in text]
 widths=[f.getlength(c) for c,f in zip(text,fonts)]
 x=center[0]*s-(sum(widths)+tracking*s*(len(text)-1))/2
 line_box=base_font.getbbox(text.replace('♥','유'))
 baseline_y=center[1]*s-(line_box[3]-line_box[1])/2-line_box[1]
 for c,f,w in zip(text,fonts,widths):
  b=f.getbbox(c)
  y=baseline_y if baseline_alignment and c!='♥' else center[1]*s-(b[3]-b[1])/2-b[1]
  # A closing corner quote belongs at the bottom of the text, not at its
  # vertical center. Keep letter/heart placement and horizontal spacing intact.
  if align_closing_quotes and c in '」』':
   y=center[1]*s+target_height/2-b[3]
  d.text((x,y),c,font=f,fill=255); x+=w+tracking*s
 return mask.resize(size,Image.Resampling.LANCZOS)

def grow(m,r):
 s=4; a=np.array(m.resize((m.width*s,m.height*s),Image.Resampling.LANCZOS)); k=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(r*s*2+1,r*s*2+1)); return Image.fromarray(cv2.dilate(a,k)).resize(m.size,Image.Resampling.LANCZOS)
def blend_color(a,target,m):
 t=np.asarray(m,dtype=float)[...,None]/255
 return a*(1-t)+np.array(target)*t
