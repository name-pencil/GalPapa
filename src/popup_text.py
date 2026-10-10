"""Translations and deterministic rendering for supplied popup/warning images."""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from paths import ROOT, SOURCE_ROOT
SOURCE = None  # Assigned by images.build.
FONT = ROOT / 'assets/fonts/Paperlogy-6SemiBold.ttf'

MESSAGE_DIALOGS = {
    'msg_koh01': '「코하룬」과 파파카츠를 하시겠습니까?',
    'msg_koh02': '「코하루」와 파파카츠를 하시겠습니까?',
    'msg_mio01': '「MIO」와 파파카츠를 하시겠습니까?',
    'msg_mio02': '「미오」와 파파카츠를 하시겠습니까?',
    'msg_yui01': '「유♥」와 파파카츠를 하시겠습니까?',
    'msg_yui02': '「유이나」와 파파카츠를 하시겠습니까?',
}


def lettering(size, lines, *, font_size=23, center=(None, None), left=None,
              line_height=32, glow=False, outline=3):
    """White text, dark outline, optional pink glow BEHIND that outline."""
    scale = 4
    canvas_size = (size[0] * scale, size[1] * scale)
    font = ImageFont.truetype(str(FONT), round(font_size * scale))
    positions = []
    cx = size[0] / 2 if center[0] is None else center[0]
    cy = size[1] / 2 if center[1] is None else center[1]
    for i, line in enumerate(lines):
        box = font.getbbox(line)
        x = (cx * scale - (box[2] - box[0]) / 2 if left is None else left * scale) - box[0]
        y = (cy + (i - (len(lines) - 1) / 2) * line_height) * scale - (box[3] - box[1]) / 2 - box[1]
        positions.append((round(x), round(y), line))
    layer = Image.new('RGBA', canvas_size)
    if glow:
        mask = Image.new('L', canvas_size)
        draw = ImageDraw.Draw(mask)
        for x, y, line in positions:
            draw.text((x, y), line, font=font, fill=210, stroke_width=round((outline + 1) * scale), stroke_fill=210)
        mask = mask.filter(ImageFilter.GaussianBlur(3.2 * scale))
        light = Image.new('RGBA', canvas_size, (247, 176, 226, 0))
        light.putalpha(mask)
        layer.alpha_composite(light)
    draw = ImageDraw.Draw(layer)
    for x, y, line in positions:
        draw.text((x, y), line, font=font, fill='white', stroke_width=round(outline * scale), stroke_fill=(42, 5, 33, 255))
    return layer.resize(size, Image.Resampling.LANCZOS)


def block(rect, text, *, size=20, glow=False, align='center', line_height=32, outline=2):
    return dict(rect=rect, text=text, size=size, glow=glow, align=align, line_height=line_height, outline=outline)


def title(rect, text, *, align='center', size=27):
    return block(rect, text, size=size, glow=True, align=align, outline=3)


POPUPS = {
    'guide01': [
        title((130, 20, 585, 67), '호감도 힌트 표시 설정'),
        block((24, 196, 690, 323), '선택지에 따른 호감도 상승을 표시할 수 있습니다.\n원활한 공략을 원하시면 이 기능을 ON으로 설정하는 것을 권장합니다.\nON으로 설정하시겠습니까?\n(환경 설정 화면에서 언제든 변경할 수 있습니다.)', size=19),
    ],
    'guide02': [
        title((70, 20, 642, 67), '스토리 클리어 후에도 파파카츠를 즐겨 보세요!', size=25),
        block((15, 266, 699, 357), '스토리를 클리어한 캐릭터와도 계속 파파카츠를 즐길 수 있습니다.\nH 장면에서 자유롭게 행동을 선택하거나 의상을 바꿀 수 있어,\n본편과는 또 다른 새로운 즐거움을 제공합니다.', size=20),
    ],
    'guide03': [
        title((155, 20, 580, 68), '엔드리스 파파카츠 모드 해금', size=26),
        block((25, 266, 710, 358), '엔드리스 파파카츠 모드에서는 스토리 클리어 후의\n행동 선택형 H 장면만 반복해서 플레이할 수 있습니다.\n타이틀의 [처음부터] → [엔드리스 파파카츠 모드]에서 즐겨 주세요.', size=20),
    ],
    'guide04': [
        title((29, 22, 245, 66), '게이지 안내', align='left'),
        title((807, 22, 1030, 66), '의상 변경', align='left'),
        block((25, 230, 393, 389), '【사정 게이지】\n남성기를 자극하면 게이지가 차오릅니다.\nMAX가 되면 테두리가 빛나며\n사정 선택지가 나타납니다.\n최대 5회 사정하면 장면이 종료됩니다.', size=19, align='left'),
        block((410, 230, 774, 451), '【절정 게이지】\n여성에게 쾌감을 주면 게이지가 차오릅니다.\nMAX가 되면 테두리가 빛납니다. 이 상태에서\n더 쾌감을 주면 램프가 최대 2개 켜지며,\n다음 클릭으로 여성이 절정에 도달합니다.\n일정 횟수 절정에 도달하면\n장면이 종료됩니다.', size=19, align='left'),
        block((805, 230, 1178, 323), '의상을 자유롭게 변경할 수 있습니다.\n스토리 모드에서는 볼 수 없었던 조합도\n즐길 수 있습니다.', size=20, align='left'),
    ],
    'job02': [
        title((198, 20, 416, 69), '부업을 하시겠습니까?', size=26),
        block((118, 173, 188, 202), '등급', align='left'),
        block((118, 204, 284, 235), '승급까지', align='left'),
        block((118, 238, 186, 268), '보수', align='left'),
        block((118, 270, 208, 300), '선택 제한', align='left'),
    ],
    'jobrankup01': [
        title((175, 20, 438, 70), '본업 등급 상승!'),
        block((135, 151, 478, 184), '본업으로 얻는 정기 수입이 증가했습니다.', size=20),
        block((125, 210, 184, 241), '등급', align='left'),
        block((125, 243, 184, 274), '급여', align='left'),
    ],
    'jobrankup02': [
        title((175, 20, 438, 70), '부업 등급 상승!'),
        block((135, 151, 478, 184), '부업으로 얻는 일시 수입이 증가했습니다.', size=20),
        block((125, 210, 184, 241), '등급', align='left'),
        block((125, 243, 184, 274), '보수', align='left'),
    ],
    'jobstatus00': [
        title((280, 20, 480, 70), '현재 상태'),
        title((161, 94, 241, 138), '본업', size=24),
        title((526, 94, 606, 138), '부업', size=24),
        block((69, 209, 138, 240), '등급', align='left'),
        block((69, 242, 132, 274), '급여', align='left'),
        block((434, 209, 504, 240), '등급', align='left'),
        block((434, 242, 504, 274), '보수', align='left'),
        block((434, 274, 524, 305), '선택 제한', align='left'),
    ],
}


def erase_text(image, rect, glow, *, ink_only=False, full_width=False):
    pixels = np.array(image)
    x0, y0, x1, y1 = rect
    crop = pixels[y0:y1, x0:x1]
    bright = crop[:, :, :3].min(axis=2) > 175
    ys = np.where(bright.any(axis=1))[0]
    if not len(ys):
        raise ValueError('Source text not found in ' + str(rect))
    groups = np.split(ys, np.where(np.diff(ys) > 5)[0] + 1)
    mask = np.zeros(pixels.shape[:2], np.uint8)
    if ink_only:
        mask[y0:y1, x0:x1] = bright.astype(np.uint8) * 255
        mask = cv2.dilate(mask, np.ones((5, 5), np.uint8))
    pad = 9 if glow else 4
    for group in ([] if ink_only else groups):
        xx = np.where(bright[group].any(axis=0))[0]
        left, right = max(x0, x0 + int(xx.min()) - pad), min(x1, x0 + int(xx.max()) + pad + 1)
        top, bottom = max(0, y0 + int(group.min()) - pad), min(image.height, y0 + int(group.max()) + pad + 1)
        mask[top:bottom, x0 if full_width else left:x1 if full_width else right] = 255
    rgb = cv2.inpaint(pixels[:, :, :3], mask, 5, cv2.INPAINT_NS)
    alpha = cv2.inpaint(pixels[:, :, 3], mask, 5, cv2.INPAINT_NS)
    return Image.fromarray(np.dstack([rgb, alpha]), 'RGBA')


def render_popup(key):
    image = Image.open(SOURCE / 'cgsys/confirm' / ('dialog_' + key + '.png')).convert('RGBA')
    for spec in POPUPS[key]:
        # Job labels extend left of the old erasure boundary.
        # Keep the star artwork at x < 116; remove the old glyph outline.
        rect = spec['rect']
        if key == 'job02' and not spec['glow']:
            rect = (116, rect[1], rect[2], rect[3])
        image = erase_text(image, rect, spec['glow'], full_width=key == 'job02' and not spec['glow'])
        x0, y0, x1, y1 = spec['rect']
        lines = spec['text'].splitlines()
        size = spec['size']
        while True:
            font = ImageFont.truetype(str(FONT), size * 4)
            width = max(font.getlength(line) / 4 for line in lines)
            if width <= x1 - x0 - 8:
                break
            size -= 1
            if size < 14:
                raise ValueError('Popup label too long: ' + key)
        image.alpha_composite(lettering(image.size, lines, font_size=size,
            center=((x0+x1)/2, (y0+y1)/2), left=(x0 + 3 if key == 'job02' and not spec['glow'] else x0) if spec['align']=='left' else None,
            line_height=spec['line_height'], glow=spec['glow'], outline=spec['outline']))
    return image


CAUTION = [
    ((345, 227, 940, 251), '본 제품은 만 18세 미만이 이용할 수 없습니다.', 20),
    ((345, 259, 940, 283), '본 작품은 허구이며, 등장하는 인물·단체는', 20),
    ((345, 291, 940, 315), '실존하는 인물·단체와 일절 관계가 없습니다.', 20),
    ((345, 354, 940, 379), '본 작품은 일본 국내에서만 판매합니다.', 20),
    ((345, 387, 940, 411), '해외 실행 환경 등에 대한 지원은 제공하지 않습니다.', 20),
    ((320, 477, 960, 498), '본 작품에 포함된 영상·이미지 등은 저작권법에 따라 저작물로서 법적 보호를 받습니다.', 14),
    ((320, 525, 960, 546), '법에 위반되는 복제, 양도, 대여, 번역, 개조, 공중송신 등의 위법 행위가 있을 경우,', 14),
    ((320, 549, 960, 570), '직접 행한 경우는 물론 타인의 행위에 관여한 경우에도', 14),
    ((320, 573, 960, 594), '민사상 손해배상 책임을 지며 형사처벌을 받을 수 있습니다.', 14),
]


def render_caution():
    original = Image.open(SOURCE / 'cg/bg/caution.png').convert('RGBA')
    image = original.copy()
    for rect, text, size in CAUTION:
        image = erase_text(image, rect, False, ink_only=True)
        x0, y0, x1, y1 = rect
        font = ImageFont.truetype(str(FONT), size * 4)
        # The copyright lines may extend beyond their original Japanese width,
        # but remain centered and within the 1,280-pixel canvas.
        assert font.getlength(text) / 4 < 1100
        image.alpha_composite(lettering(image.size, [text], font_size=size,
            center=(640, (y0+y1)/2), glow=False, outline=0))
    before, after = np.array(original), np.array(image)
    assert np.array_equal(before[417:449], after[417:449]), 'English sales notice changed'
    assert np.array_equal(before[:210], after[:210]), 'Warning icon changed'
    return image
