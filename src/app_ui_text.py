"""Translate only the plain white labels on the supplied app/status/custom screens."""
from pathlib import Path
from collections import Counter
import re
import numpy as np
from PIL import Image, ImageFont, ImageFilter
from popup_text import lettering, erase_text, FONT

from paths import ROOT, SOURCE_ROOT
SOURCE = None  # Assigned by images.build.


def label(image, rect, text, *, size=18, glow=False, outline=2, left=None, flat=False, shadow=False):
    original = np.array(image)
    x0, y0, x1, y1 = rect
    if flat:
        pixels = original.copy()
        background = Counter(map(tuple, original.reshape(-1, 4))).most_common(1)[0][0]
        pixels[y0:y1, x0:x1] = background
        result = Image.fromarray(pixels, 'RGBA')
    else:
        result = erase_text(image, rect, glow)
    while ImageFont.truetype(str(FONT), size*4).getlength(text)/4 > x1-x0-8:
        size -= 1
    layer = lettering(image.size, [text], font_size=size, center=((x0+x1)/2,(y0+y1)/2),
                      left=left, glow=glow, outline=outline)
    # Keep all artwork outside the declared text rectangle, including stars,
    # icons, bars, character portraits and decorative names, byte-for-byte.
    rendered = result.copy()
    if shadow:
        ink = lettering(image.size,[text],font_size=size,center=((x0+x1)/2,(y0+y1)/2),
                        left=left,glow=False,outline=outline)
        alpha=ink.getchannel('A').filter(ImageFilter.GaussianBlur(.6)).point(lambda a:round(a*.65))
        shade=Image.new('RGBA',image.size,(20,0,16,0));shade.putalpha(alpha)
        rendered.alpha_composite(shade,(1,1))
    rendered.alpha_composite(layer)
    if shadow:
        rect=(max(0,x0-4),max(0,y0-4),min(image.width,x1+4),min(image.height,y1+4))
        x0,y0,x1,y1=rect
    final = image.copy()
    final.paste(rendered.crop(rect), (x0,y0))
    changed = np.any(np.array(final) != original, axis=2)
    allowed = np.zeros(changed.shape, bool); allowed[y0:y1,x0:x1] = True
    assert not np.any(changed & ~allowed)
    return final


def make_app_images():
    results = []
    for path in sorted((SOURCE/'main/action_menu').glob('btn_main_chara_*.png')):
        # 9x variants are text-free endless-mode portraits; never touch them.
        if not re.search(r'_(?:koh|mio|yui)0[123]_', path.stem):
            continue
        image = Image.open(path).convert('RGBA')
        assert image.size == (398,566)
        before = np.array(image)
        glow = path.stem.endswith('_na')
        for rect,text in [((44,435,230,467),'선택 횟수'),((44,471,230,503),'스토리 진행'),((44,507,166,539),'호감도')]:
            image = label(image,rect,text,glow=glow,left=48)
        assert np.array_equal(np.array(image)[:435],before[:435]), 'Card artwork/name changed'
        results.append((path.relative_to(SOURCE).as_posix(),image,'선택 횟수 / 스토리 진행 / 호감도',dict(glow=glow)))
    for path in sorted((SOURCE/'main/sozai').glob('main_week_*.png')):
        image = label(Image.open(path).convert('RGBA'),(94,8,145,37),'주차',size=18,outline=0,flat=True)
        results.append((path.relative_to(SOURCE).as_posix(),image,'주차',{}))
    path=SOURCE/'main/sozai/main_endlessmode_00.png'
    image=label(Image.open(path).convert('RGBA'),(58,8,318,37),'엔드리스 파파카츠 모드',size=18,outline=0,flat=True)
    results.append((path.relative_to(SOURCE).as_posix(),image,'엔드리스 파파카츠 모드',{}))
    for folder,stem,text,rect in [
        ('main/action_menu','btn_status','상태 보기',(70,8,183,48)),
        ('main/or_custom_button','btn_back','닫기',(40,9,130,41)),
    ]:
        for path in sorted((SOURCE/folder).glob(stem+'_*.png')):
            active=path.stem.endswith(('_on','_over'))
            image=label(Image.open(path).convert('RGBA'),rect,text,glow=active,outline=1,flat=True,shadow=True)
            results.append((path.relative_to(SOURCE).as_posix(),image,text,dict(glow=active,shadow=True)))
    for chara in ['koharu','mio','yuina']:
        path=SOURCE/f'main/or_custom_button/portal/app_talk_{chara}_main.png'
        image=Image.open(path).convert('RGBA')
        image=label(image,(350,20,790,76),'색상 설정',size=27,glow=True,outline=3)
        for rect,text in [((374,144,431,182),'머리'),((374,213,431,252),'피부'),((374,282,431,322),'속옷')]:
            image=label(image,rect,text,left=376)
        results.append((path.relative_to(SOURCE).as_posix(),image,'색상 설정 / 머리 / 피부 / 속옷',dict(title_glow=True,body_glow=False)))
    for chara,name in [('koharu','코하루'),('mio','미오'),('yuina','유이나')]:
        for path in sorted((SOURCE/'main/or_custom_button/portal').glob('btn_app_talk_'+chara+'_*.png')):
            image=label(Image.open(path).convert('RGBA'),(25,0,111,31),name,outline=2,flat=True)
            results.append((path.relative_to(SOURCE).as_posix(),image,name,dict(glow=False,outline=True)))
    return results
