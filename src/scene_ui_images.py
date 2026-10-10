"""Dining progress and in-dialogue color panels, separate from portal UI."""
import hashlib
import numpy as np
import cv2
from PIL import Image
from restaurant_images import draw


def build(source, target, start_id):
    rows = []
    for active in range(3):
        path = f'cgsys/select/tip_talk_scene0{active + 1}.png'
        original = Image.open(source / path).convert('RGBA')
        result = original.copy()
        rects = []
        for i, text in enumerate(['식전', '식사중', '식후']):
            center = 1043 + i * 80
            rect = (center - 35, 28, center + 35, 60)
            rects.append(rect)
            if i == active:
                a = np.array(result)
                # Mask only original white glyphs and their dark outline.
                roi = a[23:64, center-47:center+47].copy()
                rgb = roi[:, :, :3]
                ink = (rgb.min(2) > 155) | ((rgb[:,:,0] < 85) & (rgb[:,:,1] < 30) & (rgb[:,:,2] < 85))
                mask = cv2.dilate(ink.astype('uint8'), np.ones((3,3), np.uint8))
                allowed = np.zeros(mask.shape, np.uint8)
                allowed[5:37,12:82] = 1
                mask *= allowed
                clean = cv2.inpaint(rgb, mask*255, 3, cv2.INPAINT_NS)
                roi[mask > 0, :3] = clean[mask > 0]
                a[23:64,center-47:center+47] = roi
                result = Image.fromarray(a)
            else:
                result.paste(original.getpixel((center,25)), (center-24,28,center+24,60))
            result = draw(result, rect, text, 20, outline=2)
        save(source, target, rows, start_id, path, original, result, rects, '식전 / 식사중 / 식후')
    for side in ['l', 'r']:
        path = f'cgsys/main/action_menu/txt_color_{side}.png'
        original = Image.open(source / path).convert('RGBA')
        result = original.copy()
        rects = []
        for center, text in zip([56,126,196], ['머리','피부','속옷']):
            rect = (46,center-15,108,center+16)
            rects.append(rect)
            result.paste(original.getpixel((110,center)), rect)
            result = draw(result, rect, text, 18, outline=2, left=48, stroke_color=(38,0,30,255))
        save(source, target, rows, start_id, path, original, result, rects, '머리 / 피부 / 속옷')
    return rows


def save(source, target, rows, start_id, path, original, result, rects, text):
    allowed = np.zeros((original.height,original.width),bool)
    for l,t,r,b in rects:
        allowed[t:b,l:r] = True
    assert np.array_equal(np.array(original)[~allowed],np.array(result)[~allowed]), path
    dest = target/path
    dest.parent.mkdir(parents=True,exist_ok=True)
    result.save(dest)
    rows.append(dict(id=start_id+len(rows),path=path,text=text,font_size=None,
                     sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),reused_from=None))
