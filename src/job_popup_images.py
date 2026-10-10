"""Actual runtime cg/pop assets, distinct from the confirm-folder previews."""
import hashlib
import numpy as np
from PIL import Image
from image_effects import mask_text, paste_effect, clip_region
from restaurant_images import draw

def build(source,target,start_id):
    rows=[]
    for path in sorted((source/'cg/pop').glob('*.png')):
        original=Image.open(path).convert('RGBA');a=np.array(original);name=path.name
        job=1 if 'job01' in name else 2
        if 'rankup' in name:
            alias=f'cgsys/confirm/dialog_jobrankup0{job}.png'
            assert np.array_equal(a,np.array(Image.open(source/alias).convert('RGBA')))
            result=Image.open(target/alias).convert('RGBA')
            text=('본업' if job==1 else '부업')+' 등급 상승! / 등급 / '+('급여' if job==1 else '보수')
            reused=142 if job==1 else 143
        else:
            clean=a.copy();rects=[(210,18,407,71),(130,144,483,187),(176,208,242,242),(176,242,236,275)]
            for x in range(210,407):
                donor=x%151
                if donor<30:donor+=453
                clean[18:71,x]=a[18:71,donor]
            for x in range(130,483):clean[144:187,x]=a[144:187,x%151]
            for x in range(176,242):clean[208:242,x]=a[208:242,x+151]
            tint=np.array([38,0,30],float)
            for y in range(242,275):
                base=a[y,552:604,:3].astype(float);inside=a[y,250:302,:3].astype(float)
                slope=np.clip(np.sum((base-tint)*(inside-tint))/np.sum((base-tint)**2),0,1)
                for x in range(176,236):
                    clean[y,x]=a[y,x+302]
                    clean[y,x,:3]=np.rint(a[y,x+302,:3]*slope+tint*(1-slope)).astype('uint8')
            result=Image.fromarray(clean)
            heading='급여 GET!' if job==1 else '보수 GET!'
            body='본업으로 정기 수입을 얻었습니다.' if job==1 else '부업으로 일시 수입을 얻었습니다.'
            result=clip_region(result,paste_effect(result,mask_text(original.size,heading,27,(306,44)),'popup'),rects[0])
            result=draw(result,rects[1],body,20,outline=2)
            result=draw(result,rects[2],'등급',20,outline=2,left=179)
            result=draw(result,rects[3],'급여' if job==1 else '보수',20,outline=2,left=179)
            allowed=np.zeros(a.shape[:2],bool)
            for l,t,r,b in rects:allowed[t:b,l:r]=True
            assert np.array_equal(a[~allowed],np.array(result)[~allowed]),name
            text=heading+' / '+body+' / 등급 / '+('급여' if job==1 else '보수');reused=None
        rel='cg/pop/'+name;dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);result.save(dest)
        rows.append(dict(id=start_id+len(rows),path=rel,text=text,font_size=None,reused_from=reused,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
    assert len(rows)==18
    return rows
