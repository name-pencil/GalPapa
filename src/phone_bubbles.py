"""Fit original bubble silhouettes to Korean ink while preserving script coordinates."""
import math
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from paths import ROOT
FONT=ROOT/'assets/fonts/Paperlogy-5Medium.ttf'


def nine_slice(tile,size,caps):
    w,h=size;left,top,right,bottom=caps
    assert w>=left+right and h>=top+bottom
    result=Image.new('RGBA',size)
    sx=[0,left,tile.width-right,tile.width];sy=[0,top,tile.height-bottom,tile.height]
    dx=[0,left,w-right,w];dy=[0,top,h-bottom,h]
    for yy in range(3):
        for xx in range(3):
            tw,th=dx[xx+1]-dx[xx],dy[yy+1]-dy[yy]
            if not tw or not th:continue
            piece=tile.crop((sx[xx],sy[yy],sx[xx+1],sy[yy+1]))
            assert piece.width and piece.height
            result.paste(piece.resize((tw,th),Image.Resampling.NEAREST),(dx[xx],dy[yy]))
    return result


def render(original,spec,return_layout=False):
    a=np.array(original);l,t,r,b=spec['bubble_rect'];bg=tuple(spec['background'])
    right=bg[1]>bg[0]+50 or bg[0]>bg[1]+50
    lines=spec['text'].split('\n');assert len(lines)==len(spec['source_line_bands'])
    scale=4;font=ImageFont.truetype(str(FONT),12*scale);glyphs=[]
    for line in lines:
        box=font.getbbox(line)
        mask=Image.new('L',(math.ceil(font.getlength(line))+16,box[3]-box[1]+16))
        ImageDraw.Draw(mask).text((8-box[0],8-box[1]),line,font=font,fill=255)
        box=mask.getbbox();assert box,line;glyphs.append(mask.crop(box))
    glyph_height=max(x.height for x in glyphs);pitch=16*scale
    block_height=glyph_height+(len(lines)-1)*pitch
    width=max(28,math.ceil(max(x.width for x in glyphs)/scale)+16)
    height=max(27,math.ceil(block_height/scale)+16)
    assert width<=r-l+2,(spec['review_id'],width,r-l)
    nl=r-width if right else l;nt=t;nr=nl+width;nb=nt+height
    assert 0<=nl and nr<=original.width,(spec['review_id'],(nl,nt,nr,nb),original.size)
    _,labels=cv2.connectedComponents((a[:,:,3]>0).astype('uint8'),8)
    label=labels[(t+b)//2,(l+r)//2];assert label
    bubble=labels==label;ys,xs=np.where(bubble)
    x0,y0,x1,y1=int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1
    assert l-14<=x0<=l and r<=x1<=r+14 and t-3<=y0<=t and b<=y1<=b+3,(spec['review_id'],(x0,y0,x1,y1),spec['bubble_rect'])
    detached=(a[:,:,3]>0)&(~bubble)
    detached[:max(0,t-8)]=False;detached[min(original.height,b+8):]=False
    if right:detached[:,l:]=False
    else:detached[:,:r]=False
    my=np.where(detached)[0]
    bottom_margin=max(y1-b,int(my.max())+1-b if len(my) else 0)
    height=min(height,original.height-t-bottom_margin);nb=t+height
    assert height*scale-block_height>=14*scale,(spec['review_id'],height,block_height/scale)
    clean=original.copy();clean.paste(bg,(l+4,t+4,r-4,b-4))
    isolated=np.array(clean);isolated[~bubble]=0
    tile=Image.fromarray(isolated).crop((x0,y0,x1,y1))
    caps=(l-x0+12,t-y0+19,x1-r+12,y1-b+7)
    new_tile=nine_slice(tile,(width+l-x0+x1-r,height+t-y0+y1-b),caps)
    new_x,new_y=nl-(l-x0),nt-(t-y0)
    result=original.copy()
    if bg[1]>bg[0]+50:
        read=(max(0,l-30),b-18,max(0,l-3),b-9)
        if np.any(a[read[1]:read[3],read[0]:read[2],3]>0):
            result.paste((0,0,0,0),read);rf=ImageFont.truetype(str(FONT),7*scale)
            labelim=Image.new('RGBA',((read[2]-read[0])*scale,(read[3]-read[1])*scale))
            ImageDraw.Draw(labelim).text((labelim.width-rf.getlength('읽음'),-rf.getbbox('읽음')[1]),'읽음',font=rf,fill=(140,140,140,255))
            result.alpha_composite(labelim.resize((read[2]-read[0],read[3]-read[1]),Image.Resampling.LANCZOS),read[:2])
    arr=np.array(result);arr[bubble]=0
    meta=np.zeros(arr.shape[:2],bool)
    if right:meta[max(0,t-8):min(original.height,b+8),:l]=True
    else:meta[max(0,t-8):min(original.height,b+8),r:]=True
    meta &= arr[:,:,3]>0
    ys,xs=np.where(meta);metadata=None
    if len(xs):
        mr=(int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1)
        layer=arr.copy();layer[~meta]=0;metadata=Image.fromarray(layer).crop(mr);arr[meta]=0
    result=Image.fromarray(arr);result.alpha_composite(new_tile,(new_x,new_y))
    if metadata:
        shift_x=nl-l if right else nr-r;shift_y=nb-b
        assert 0<=mr[0]+shift_x and mr[2]+shift_x<=original.width and 0<=mr[1]+shift_y and mr[3]+shift_y<=original.height,spec['review_id']
        result.alpha_composite(metadata,(mr[0]+shift_x,mr[1]+shift_y))
    textmask=Image.new('L',(width*scale,height*scale));top=(height*scale-block_height)//2
    for i,mask in enumerate(glyphs):
        x=width*scale-8*scale-mask.width if right else 8*scale
        y=top+i*pitch+(glyph_height-mask.height)//2
        textmask.paste(mask,(x,y))
    ink=Image.new('RGBA',textmask.size,(75,72,73,255));ink.putalpha(textmask)
    result.alpha_composite(ink.resize((width,height),Image.Resampling.LANCZOS),(nl,nt))
    layout=dict(review_id=spec['review_id'],side='right' if right else 'left',original_rect=[l,t,r,b],new_rect=[nl,nt,nr,nb],line_count=len(lines),padding=8,ink_width=max(x.width for x in glyphs)/scale,ink_height=block_height/scale)
    return (result,layout) if return_layout else result
