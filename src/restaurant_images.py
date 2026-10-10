"""Restaurant selection/order images. Preserve prices, English logos and artwork outside ink."""
from pathlib import Path
import re,hashlib,collections,json
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from paths import ROOT,SOURCE_ROOT
FONT=ROOT/'assets/fonts/Paperlogy-6SemiBold.ttf'
GLOSSARY=json.loads((ROOT/'translation/glossary_v1.json').read_text(encoding='utf-8'))
SHOP_NAMES={1:GLOSSARY['ＧＹＵＧＹＵめし'],2:GLOSSARY['デリシャ～ス'],3:GLOSSARY['ステラ'],4:GLOSSARY['ジュワジュワカーニバル'],5:GLOSSARY['テゾーロ'],6:GLOSSARY['武者小路']}
SHOPS={1:['규동 체인점',f'「{SHOP_NAMES[1]}」'],2:['패밀리 레스토랑',f'「{SHOP_NAMES[2]}」'],3:['카페'],4:['BBQ 테라스',f'「{SHOP_NAMES[4]}」'],5:['라운지',f'「{SHOP_NAMES[5]}」'],6:['고급 스시집',f'「{SHOP_NAMES[6]}」']}
FOOD={1:['늘 먹던 규동',GLOSSARY['大豆ミート牛丼'],GLOSSARY['おつゆだくだくこぼれ牛丼'],'스페셜 카레'],2:[GLOSSARY['とろとろ～んチーズインハンバーグ'],GLOSSARY['野菜まみれのヘルシー御膳'],GLOSSARY['おどろき惣菜パフェ'],GLOSSARY['お子様じゃないプレート']],3:[GLOSSARY['自家製パンチェッタのカルボナーラ'],GLOSSARY['濃厚デミグラオムライス'],GLOSSARY['チキンシーザーサラダボウル'],GLOSSARY['わがままチーズフォンデュ']],4:['스페어립',GLOSSARY['野菜とキノコの塩焼きそば'],'해산물 빠에야','최상급 샤토브리앙'],5:[GLOSSARY['黒毛和牛特選サーロインステーキ'],GLOSSARY['ロブスター黄金姿焼き'],GLOSSARY['鯛と帆立のムニエル～旬の野菜を添えて～'],GLOSSARY['シェフのスペシャリテ']],6:['참치 모둠 초밥',GLOSSARY['炙り握り'],'특상 오마카세 초밥',GLOSSARY['極楽浄土コース']]}

def draw(im,rect,text,size=22,color=(255,255,255,255),outline=0,left=None,stroke_color=None):
 x0,y0,x1,y1=rect;scale=4;layer=Image.new('RGBA',((x1-x0)*scale,(y1-y0)*scale));font=ImageFont.truetype(str(FONT),size*scale);d=ImageDraw.Draw(layer);b=font.getbbox(text)
 assert font.getlength(text)/scale <= x1-x0-2,str((text,rect))
 x=(layer.width-font.getlength(text))/2 if left is None else (left-x0)*scale
 y=(layer.height-(b[3]-b[1]))/2-b[1]
 d.text((x,y),text,font=font,fill=color,stroke_width=outline*scale,stroke_fill=stroke_color or (22,0,17,255))
 im.alpha_composite(layer.resize((x1-x0,y1-y0),Image.Resampling.LANCZOS),(x0,y0));return im

def erase(im,reference,rect):
 x0,y0,x1,y1=rect;a=np.array(im);ref=np.array(reference);sub=ref[y0:y1,x0:x1]
 dark=np.all(sub[:,:,:3]==(38,0,30),2)&(sub[:,:,3]>80)
 bright=(sub[:,:,:3].min(2)>175)&(sub[:,:,3]>80)
 if dark.sum()>50:
  near=cv2.dilate(dark.astype('uint8'),np.ones((9,9),np.uint8))>0
  ink=dark|(bright&near)
 else:ink=bright
 mask=cv2.dilate(ink.astype('uint8')*255,np.ones((5,5),np.uint8))
 roi=a[y0:y1,x0:x1].copy();rgb=cv2.inpaint(roi[:,:,:3],mask,3,cv2.INPAINT_NS)
 # Alpha itself is restored from neighbors, needed for transparent menu states.
 alpha=cv2.inpaint(roi[:,:,3],mask,3,cv2.INPAINT_NS)
 roi[mask>0]=np.dstack([rgb,alpha])[mask>0];a[y0:y1,x0:x1]=roi
 return Image.fromarray(a)

def restore_header(im,reference,rect):
 # Header backing is alpha 197; lettering and outline raise alpha above it.
 # Work with a padded region so inpainting can see clean backing on all sides.
 x0,y0,x1,y1=rect;l=max(0,x0-10);t=max(0,y0-8);r=min(im.width,x1+10);b=min(im.height,y1+8)
 a=np.array(im);ref=np.array(reference)[t:b,l:r];mask=(ref[:,:,3]>197).astype('uint8')
 mask=cv2.dilate(mask,np.ones((3,3),np.uint8));allowed=np.zeros(mask.shape,np.uint8);allowed[max(0,y0-t-4):y1-t+4,max(0,x0-l-4):x1-l+4]=1;mask*=allowed
 roi=a[t:b,l:r];rgb=cv2.inpaint(roi[:,:,:3],mask*255,3,cv2.INPAINT_NS)
 roi[mask>0,:3]=rgb[mask>0];roi[mask>0,3]=197
 return Image.fromarray(a)

def restore_shop(im,original,reference,rect,photo):
 x0,y0,x1,y1=rect;pad=24;l=max(0,x0-pad);t=max(0,y0-pad);r=min(im.width,x1+pad);b=min(im.height,y1+pad)
 original_a=np.array(original);ref=np.array(reference)[t:b,l:r];actual=original_a[t:b,l:r];donor=photo[t:b,l:r].astype('float32')
 dark=np.all(ref[:,:,:3]==(38,0,30),2)&(ref[:,:,3]>200)
 near=cv2.dilate(dark.astype('uint8'),np.ones((9,9),np.uint8))>0
 ink=cv2.dilate((dark|((ref[:,:,:3].min(2)>175)&near)).astype('uint8'),np.ones((5,5),np.uint8))>0
 valid=((~ink)&(actual[:,:,3]>240)).astype('float32');pixels=actual[:,:,:3].astype('float32')
 def box(a):return cv2.boxFilter(a,-1,(41,41),normalize=False,borderType=cv2.BORDER_REFLECT)
 count=np.maximum(box(valid),1)[...,None];mx=box(donor*valid[...,None])/count;my=box(pixels*valid[...,None])/count
 var=(box(donor*donor*valid[...,None])-count*mx*mx).sum(2)
 cov=(box(donor*pixels*valid[...,None])-count*mx*my).sum(2)
 slope=np.clip(cov/np.maximum(var,1),0,1.5)[...,None]
 restored=np.clip(np.rint(slope*donor+my-slope*mx),0,255).astype('uint8')
 target=np.array(im);region=target[t:b,l:r];allowed=np.zeros(ink.shape,bool);allowed[y0-t:y1-t,x0-l:x1-l]=True;mask=ink&allowed
 region[mask,:3]=restored[mask];target[t:b,l:r]=region
 return Image.fromarray(target)

DESCRIPTIONS={
1:(f'규동 체인점 「{SHOP_NAMES[1]}」','「든든하게 한 끼, 매일 찾는 맛.」','푸짐한 양과 진한 양념이 중독되는 서민적인 규동 체인점. 주문 즉시 나오는 빠른 음식과 부담 없는 가격이 가장 큰 무기다. 단순하지만 한결같이 맛있다. 그것만으로 충분하다.'),
2:(f'패밀리 레스토랑 「{SHOP_NAMES[2]}」','「다 함께 즐기는 맛있는 한 끼.」','밝고 경쾌한 분위기에 푸짐한 메뉴를 갖춘 인기 패밀리 레스토랑. 기본 함박스테이크부터 색다른 별미까지 폭넓게 즐길 수 있다. 부담 없이 들러 만족스럽게 먹을 수 있는 든든한 일상의 식당.'),
3:(f'카페 「{SHOP_NAMES[3]}」','「느긋하게 쉬어 갈 수 있는 곳.」','까르보나라와 오므라이스 등 양식 메뉴가 다양한 캐주얼 카페. 식사부터 디저트와 음료까지 갖춰 점심에도 티타임에도 들르기 좋다. 세련된 인테리어와 자꾸 오래 머물게 되는 편안함이 매력이다.'),
4:(f'BBQ 테라스 「{SHOP_NAMES[4]}」','「굽고, 먹고, 또 굽고.」','탁 트인 테라스에서 푸짐하게 구워 먹는 바비큐 레스토랑. 국내산 소고기부터 해산물까지 재료도 다양하다. 숯불 향과 친구들의 웃음소리가 어우러지는 축제 같은 활기가 매력이다.'),
5:(f'라운지 「{SHOP_NAMES[5]}」','「보물 같은 한 접시가 기다린다.」','엄선한 재료로 만든 창작 요리를 즐길 수 있는 어른의 다이닝 라운지. 세련된 공간에서 맛보는 요리는 하나같이 섬세하고 깊은 풍미를 지녔다. 음미할수록 맛이 풍성해지는, 특별한 밤에 어울리는 잔잔한 감동이 있다.'),
6:(f'고급 스시집 「{SHOP_NAMES[6]}」','「갈고닦은 한 점이 이야기를 전한다.」','전국 어항에서 직송한 엄선된 제철 재료를 능숙한 손길로 쥐어 내는 에도마에 스시의 명점. 편백나무 카운터 너머 장인의 차분한 태도가 이곳의 품격을 더욱 높여 준다.')}

def description(im,original,donor,n):
 from phone_images import wrap
 rect=(903,423,1275,626);overlay=original.getpixel((1250,625))
 clean=Image.new('RGBA',original.size,overlay) if donor is None else Image.alpha_composite(donor,Image.new('RGBA',donor.size,overlay));im.paste(clean.crop(rect),rect[:2])
 title,tagline,body=DESCRIPTIONS[n]
 im=draw(im,(905,425,1273,452),title,18,outline=2,left=907)
 font=ImageFont.truetype(str(FONT),18*4)
 lines=[tagline]+wrap(body,font,(1272-907)*4)
 assert len(lines)<=7,(n,len(lines))
 for i,line in enumerate(lines):im=draw(im,(905,464+i*22,1273,487+i*22),line,18,outline=2,left=907)
 return im,' / '.join([title,tagline,body])

def build(source,target,start_id,progress=None):
 folder=source/'cgsys/main/slg/restaurant';rows=[];cache={};photos={};early_cache={}
 backgrounds=json.loads((SOURCE_ROOT/'restaurant_backgrounds.json').read_text(encoding='utf-8'))
 for number,spec in backgrounds.items():
  a=np.array(Image.open(source/spec['path']).convert('RGB'));photos[int(number)]=cv2.warpAffine(a,np.array(spec['transform']),(1280,720),flags=cv2.INTER_LINEAR)
 for path in sorted(folder.rglob('*.png')):
  name=path.name;im=Image.open(path).convert('RGBA');before=im.copy();texts=[]
  source_key=hashlib.sha256(im.tobytes()+str(im.size).encode()).hexdigest()
  if source_key in early_cache:
   old,previous=early_cache[source_key];relative=path.relative_to(source).as_posix();dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(previous.read_bytes())
   rows.append({**old,'id':start_id+len(rows),'path':relative,'reused_from':old['id']})
   if progress:progress(len(rows))
   continue
  food=re.fullmatch(r'btn_restaurant0([1-6])_menu([012][1-4])(?:_2)?_(off|on|over|na)\.png',name)
  shop=re.fullmatch(r'btn_restaurant([0-3][1-6])_(off|on|over|na)\.png',name)
  if food and '_2_' in name:
   # Locked menu artwork is already language-neutral: preserve every pixel.
   texts=['???']
  elif food:
   n,item,state=int(food[1]),int(food[2])%10,food[3];text=FOOD[n][item-1]
   ref=Image.open(folder/'menu'/f'btn_restaurant0{n}_menu0{item}_off.png').convert('RGBA')
   a=np.array(ref);coin=(a[:,:,0]>80)&(a[:,:,1]>80)&(a[:,:,2]<np.minimum(a[:,:,0],a[:,:,1])*.8)&(a[:,:,3]>0);xs=np.where(coin[12:48,450:].sum(0)>2)[0]
   edge=min(497,450+int(xs.min())-3) if len(xs) else 497
   rect=(12,8,440 if n==1 else edge,52)
   ref=Image.open(folder/'menu'/f'btn_restaurant0{n}_menu0{item}_off.png').convert('RGBA')
   if n==6:im=erase(im,ref,rect)
   else:
    a=np.array(im);x0,y0,x1,y1=rect
    if n==1:
     background=collections.Counter(map(tuple,a[y0:y1,x0:x1].reshape(-1,4))).most_common(1)[0][0];a[y0:y1,x0:x1]=background
    else:
     for y in range(y0,y1):a[y,x0:x1]=collections.Counter(map(tuple,a[y,15:x1])).most_common(1)[0][0]
    im=Image.fromarray(a)
   face={1:(18,18,18),2:(255,255,183),3:(255,255,255),4:(191,174,155),5:(255,255,255),6:(255,255,255)}[n]
   ref_a=np.array(ref)[12:48,24:430];current_a=np.array(before)[12:48,24:430]
   ink=np.all(ref_a[:,:,:3]==face,2)&(ref_a[:,:,3]==255)
   if not ink.any():ink=ref_a[:,:,:3].min(2)>220
   color=collections.Counter(map(tuple,current_a[ink])).most_common(1)[0][0]
   stroke=None
   if n==1:
    white=np.all(ref_a[:,:,:3]==255,2);stroke=collections.Counter(map(tuple,current_a[white])).most_common(1)[0][0]
   im=draw(im,rect,text,20 if n==5 and item==3 else 24,color,2 if n==1 else 0,left=23,stroke_color=stroke);texts=[text]
   if n!=6:assert np.array_equal(np.array(im)[:,rect[2]:],np.array(before)[:,rect[2]:]),name
   if n==6:
    price=(562,8,640,52);im=erase(im,ref,price);im=draw(im,price,'시가',22,color);texts.append('시가')
  elif shop:
   n=int(shop[1])%10;state=shop[2];col=(n-1)//3;row=(n-1)%3;x=60+320*col;y=181+168*row
   ref=Image.open(folder/f'btn_restaurant0{n}_off.png').convert('RGBA')
   # Restore both source lines together before drawing; overlapping erase
   # rectangles previously cut into the freshly rendered Korean first line.
   im=restore_shop(im,before,ref,(x-6,y-20,x+268,y+52 if n!=3 else y+18),photos[n])
   for j,text in enumerate(SHOPS[n]):
    rect=(x-4,y-14+j*24,x+255,y+14+j*24)
    im=draw(im,rect,text,20,(85,85,85,255) if state=='na' else (255,255,255,255),2,left=x);texts.append(text)
   if state in ('on','over'):
    donor=Image.open(folder/f'btn_restaurant9{int(shop[1])//10}_off.png').convert('RGBA') if int(shop[1])>=10 else None
    im,detail=description(im,before,donor,n);texts.append(detail)
  elif name in ['restaurant_back.png','restaurant_back00.png','restaurant_back01.png','restaurant_back02.png','restaurant_back04.png']:
   for rect,text,sz in [((37,89,172,126),'가게 선택',26),((203,91,301,125),'활동비',22)]:im=draw(restore_header(im,before,rect),rect,text,sz,outline=2);texts.append(text)
   if name in ['restaurant_back.png','restaurant_back01.png','restaurant_back04.png']:
    rect=(462,91,563,125);im=draw(restore_header(im,before,rect),rect,'관계 없음:',20,outline=2);texts.append('관계 없음:')
  elif name in ['menu_back01.png','menu_back03.png','menu_back06.png']:
   rect=(530,185,752,237)
   # Cafe: erase only MENU lettering between the original bean ornaments.
   if name=='menu_back03.png':
    rect=(573,185,706,237);im.paste((255,255,255,255),rect)
   else:
    a=np.array(im);a[185:237,530:752]=a[185:237,330:552];im=Image.fromarray(a)
   im=draw(im,rect,'메뉴' if name!='menu_back06.png' else '차림표',34,(30,30,30,255));texts=['메뉴' if name!='menu_back06.png' else '차림표']
  if not texts:continue
  relative=path.relative_to(source).as_posix();dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True)
  key=hashlib.sha256(before.tobytes()+str(texts).encode()).hexdigest();reuse=cache.get(key)
  if reuse:im=Image.open(reuse[1]).convert('RGBA')
  else:cache[key]=(start_id+len(rows),dest)
  im.save(dest);rows.append({'id':start_id+len(rows),'path':relative,'text':' / '.join(texts),'font_size':None,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'reused_from':reuse[0] if reuse else None})
  early_cache[source_key]=(rows[-1].copy(),dest)
  if progress:progress(len(rows))
 return rows
