"""Reconstruct label backgrounds from matching text-free original cards."""
import numpy as np
import cv2
from PIL import Image
from popup_text import lettering
RECTS=[((45,435,230,467),'선택 횟수'),((45,471,230,503),'스토리 진행'),((45,507,166,539),'호감도')]

def label_layer():
 layer=Image.new('RGBA',(398,566))
 for (x0,y0,x1,y1),text in RECTS:
  layer.alpha_composite(lettering(layer.size,[text],font_size=18,center=((x0+x1)/2,(y0+y1)/2),left=48,glow=False,outline=2))
 return layer

def render(source,donor,layer):
 a=np.array(source);b=np.array(donor);rects=RECTS
 mask=np.zeros(a.shape[:2],np.uint8);mask[100:430,100:325]=255
 sift=cv2.SIFT_create();ka,da=sift.detectAndCompute(cv2.cvtColor(a,cv2.COLOR_RGBA2GRAY),mask);kb,db=sift.detectAndCompute(cv2.cvtColor(b,cv2.COLOR_RGBA2GRAY),mask)
 good=[]
 if da is not None and db is not None and len(da)>1:
  good=[m for m,n in cv2.BFMatcher().knnMatch(db,da,k=2) if m.distance<.7*n.distance]
 if len(good)>12:
  src=np.float32([kb[m.queryIdx].pt for m in good]);dst=np.float32([ka[m.trainIdx].pt for m in good])
  offset=np.median(dst-src,axis=0)
  match_error=float(np.median(np.linalg.norm(src+offset-dst,axis=1)))
  assert np.max(np.abs(offset))<2 and match_error<.8
 else:
  # Silhouette variants have too few features. Their replacement areas
  # are flat background; preserve the original pixels wherever possible.
  offset=np.zeros(2);match_error=None
 aligned=cv2.warpAffine(b,np.array([[1,0,offset[0]],[0,1,offset[1]]],np.float32),(398,566),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
 donor=Image.fromarray(aligned)
 clean=source.copy()
 for rect,_ in rects:clean.paste(donor.crop(rect),rect[:2])
 rendered=Image.alpha_composite(clean,layer);result=source.copy()
 for rect,_ in rects:result.paste(rendered.crop(rect),rect[:2])
 allowed=np.zeros(a.shape[:2],bool)
 for (x0,y0,x1,y1),_ in rects:allowed[y0:y1,x0:x1]=True
 assert np.array_equal(np.array(result)[~allowed],a[~allowed])
 for y in [435,471,507]:assert np.array_equal(np.array(result)[y:y+32,24:45],a[y:y+32,24:45])
 return result
