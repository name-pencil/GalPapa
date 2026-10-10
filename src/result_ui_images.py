"""Result popup labels; retain icons, stars and both gauge variants."""
import hashlib
import numpy as np
from PIL import Image
from image_effects import mask_text, paste_effect, clip_region

def build(source,target,start_id):
    rows=[]
    for name in ['result_back.png','result_back2.png']:
        path='cgsys/main/result/'+name
        original=Image.open(source/path).convert('RGBA');a=np.array(original);clean=a.copy()
        rects=[(210,18,405,68),(92,177,166,210),(92,209,228,243)]
        for x in range(210,405):
            donor=x%151
            if donor<30:donor+=453
            clean[18:68,x]=a[18:68,donor]
        # The background repeats every 151px. Choose unobstructed donor pixels;
        # where the donor is outside the dark panel, restore its overlay too.
        tint=np.array([38,0,30],float)
        for y in range(177,210):
            base=a[y,0:56,:3].astype(float);inside=a[y,453:509,:3].astype(float)
            slope=np.clip(np.sum((base-tint)*(inside-tint))/np.sum((base-tint)**2),0,1)
            for x in range(92,166):
                donor=x+453 if x<119 else x+302
                clean[y,x]=a[y,donor]
                if donor>=555:clean[y,x,:3]=np.rint(a[y,donor,:3]*slope+tint*(1-slope)).astype('uint8')
        for x in range(92,228):
            donor=x+151 if x<207 else x+302
            clean[209:243,x]=a[209:243,donor]
        result=Image.fromarray(clean)
        for rect,text,size,center in [(rects[0],'대화 결과',27,(306,44)),(rects[1],'호감도',18,(124,193)),(rects[2],'스토리 진행',18,(150,225))]:
            mask=mask_text(original.size,text,size,center)
            if size==18:
                ink_left=int(np.where(np.array(mask)>127)[1].min())
                shifted=Image.new('L',original.size);shifted.paste(mask,(96-ink_left,0));mask=shifted
            result=clip_region(result,paste_effect(result,mask,'popup'),rect)
        allowed=np.zeros(a.shape[:2],bool)
        for l,t,r,b in rects:allowed[t:b,l:r]=True
        assert np.array_equal(a[~allowed],np.array(result)[~allowed]),name
        dest=target/path;dest.parent.mkdir(parents=True,exist_ok=True);result.save(dest)
        rows.append(dict(id=start_id+len(rows),path=path,text='대화 결과 / 호감도 / 스토리 진행',font_size=None,sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),reused_from=None))
    return rows
