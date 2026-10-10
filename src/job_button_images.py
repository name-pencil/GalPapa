"""Side-job action and cooldown button labels used by yst00156."""
import hashlib
import cv2
import numpy as np
from PIL import Image
from restaurant_images import draw


def erase_label(image,rect,donor=None):
    a=np.array(image);l,t,r,b=rect;roi=a[t:b,l:r].copy();rgb=roi[:,:,:3]
    white=(rgb.min(2)>175)&(roi[:,:,3]>180)
    near=cv2.dilate(white.astype('uint8'),np.ones((11,11),np.uint8))>0
    dark=(rgb[:,:,0]<85)&(rgb[:,:,1]<35)&(rgb[:,:,2]<85)
    mask=cv2.dilate((white|(dark&near)).astype('uint8'),np.ones((3,3),np.uint8))
    clean=cv2.inpaint(rgb,mask*255,3,cv2.INPAINT_NS) if donor is None else donor[t:b,l:r,:3]
    roi[mask>0,:3]=clean[mask>0];a[t:b,l:r]=roi
    return Image.fromarray(a)


def build(source,target,start_id):
    folder=source/'cgsys/main/action_menu';rows=[]
    off=Image.open(folder/'btn_job02_off.png').convert('RGBA')
    clean_off=np.array(erase_label(off,(108,30,226,76)))
    for path in sorted(folder.glob('btn_job02*.png')):
        if path.name=='btn_job02_na.png':continue  # Original is fully transparent.
        original=Image.open(path).convert('RGBA');a=np.array(original)
        if '_na_' in path.name:
            text=path.stem[-1]+'주 후 가능';rect=(47,30,232,76)
            # Recover the obscured coin from the normal state, matching the
            # disabled-state tint using clean background pixels above the label.
            donor=clean_off.copy()
            for c in range(3):
                x=np.array(off)[20:32,45:230,c].astype(float).ravel();y=a[20:32,45:230,c].astype(float).ravel()
                slope,offset=np.linalg.lstsq(np.column_stack([x,np.ones(len(x))]),y,rcond=None)[0]
                donor[:,:,c]=np.clip(np.rint(clean_off[:,:,c]*slope+offset),0,255)
            result=erase_label(original,rect,donor);center_rect=(108,32,234,73);size=24;left=None
        else:
            text='부업하기';rect=(108,30,226,76)
            result=erase_label(original,rect);center_rect=(108,28,226,71);size=26;left=110
        result=draw(result,center_rect,text,size,left=left,outline=2,stroke_color=(38,0,30,255))
        allowed=np.zeros(a.shape[:2],bool);l,t,r,b=rect;allowed[t:b,l:r]=True
        assert np.array_equal(a[~allowed],np.array(result)[~allowed]),path.name
        rel='cgsys/main/action_menu/'+path.name;dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);result.save(dest)
        rows.append(dict(id=start_id+len(rows),path=rel,text=text,font_size=size,reused_from=None,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
    assert len(rows)==6
    return rows
