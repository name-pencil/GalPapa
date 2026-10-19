"""Endless-mode labels. Rebuild from originals; retain all pixels outside labels."""
import hashlib
import re
import numpy as np
from PIL import Image, ImageFont
from restaurant_images import draw, FONT
from scene_ui_images import save
from image_effects import mask_text, paste_effect, clip_region

ACTIONS = {
    'btn_command_01': '성기를 빼낸다',
    'tab_btn_fellatio': '입에 물어 달라고 한다', 'tab_btn_handjob': '손으로 해 달라고 한다',
    'tab_btn_insertion': '삽입한다', 'tab_btn_insertionanal': '삽입한다 (애널)',
    'tab_btn_insertionseiki': '삽입한다 (성기)', 'tab_btn_inside': '사정',
    'tab_btn_irrumatio': '이라마치오', 'tab_btn_kiss02': '키스한다',
    'tab_btn_lick': '핥아 달라고 한다', 'tab_btn_outside': '사정 (밖에)',
    'tab_btn_paizuri': '파이즈리', 'tab_btn_press': '프레스한다',
    'tab_btn_yubianal': '애널을 만진다', 'tab_btn_yubiseikiire': '성기에 손가락을 넣는다',
    'tab_btn_change': '체위 변경', 'tab_btn_end01': '그만둔다',
    'btn_puthalf': '반탈의', 'btn_putoff': '없음', 'btn_puton': '착의',
    'btn_sei': '교복', 'btn_shi': '사복',
}
POSITIONS = {
    'a': ['펠라', '후배 기승위', '파이즈리', '정상위', '후배위', '입위'],
    'b': ['손으로', '펠라', '정상위', '후배위', '측위', '기승위'],
    'c': ['펠라', '정상위', '69', '후배위', '기승위', '들박'],
}


def flat_label(result, original, rect, text, size, sample, *, outline=2, align='center'):
    """Restore a flat backing, then place ink by its visible bounding box."""
    result.paste(original.getpixel(sample), rect)
    font = ImageFont.truetype(str(FONT), size * 4)
    width = font.getlength(text) / 4
    assert width + 2 * outline + 4 <= rect[2] - rect[0], (text, rect)
    left = rect[0] + outline + 2 if align == 'left' else None
    if align == 'right':
        left = rect[2] - outline - 2 - width
    return draw(result, rect, text, size, outline=outline, left=left,
                stroke_color=(38, 0, 30, 255))


def render(original, relative):
    name = relative.rsplit('/', 1)[-1]
    stem = re.sub(r'_(?:off_na|on_na|off|onover|on|over)\.png$', '', name)
    result = original.copy()
    rects = []
    text = None
    if '/h_button/' in relative:
        m = re.fullmatch(r'h_btn_cg_([abc])0([1-6])_(off|on|over)\.png', name)
        if not m:
            return None
        text = POSITIONS[m[1]][int(m[2]) - 1]
        # Capsule occupies y=104..132, centered at (121.5, 118.5).
        # Keep erasure inside its flat interior: y=133 is already artwork.
        rects = [(53, 106, 190, 131)]
        result = flat_label(result, original, rects[0], text, 18, (52, 119), outline=0)
    elif stem in ACTIONS:
        text = ACTIONS[stem]
        if original.width == 600:
            # One sprite contains BOTH left- and right-docked copies.
            rects = [(10, 6, 285, 34), (315, 6, 590, 34)]
            for rect, align in zip(rects, ['left', 'right']):
                result = flat_label(result, original, rect, text, 18, (300, 20), align=align)
        elif stem.startswith('btn_put'):
            rects = [(39, 0, original.width, 32)]
            result = flat_label(result, original, rects[0], text, 18, (original.width-1, 0))
            if name.endswith('_na.png'):
                # Disabled sprites are the same art with uniformly reduced alpha.
                a = np.array(result); a[:, 39:, 3] = np.rint(a[:, 39:, 3] * .1).astype('uint8')
                result = Image.fromarray(a)
        elif stem in ('btn_sei', 'btn_shi'):
            rects = [(40, 4, 96, 30)]
            result = flat_label(result, original, rects[0], text, 18, (35, 16))
        else:
            rects = [(10, 4, original.width-10, 36)]
            result = flat_label(result, original, rects[0], text, 18, (10, 18))
    elif name.startswith(('txt_cloth_ptn', 'txt_cloth_sit')):
        labels = ['상의', '하의', '속옷 (위)', '속옷 (아래)']
        if 'ptnb' in name: labels.append('양말')
        if 'ptnc' in name: labels.append('스타킹')
        text = ' / '.join(labels)
        for i, label in enumerate(labels):
            cy = 76 + 59 * i
            rect = (48, cy-17, 190, cy+18)
            rects.append(rect)
            result = flat_label(result, original, rect, label, 20, (200, cy), align='left')
    elif name in ('s_gauge_front.png', 's_gauge_finish_front.png',
                  'z_gauge_front.png', 'z_gauge_finish_front.png'):
        text = '사정' if name.startswith('s_') else '절정'
        rects = [(22, 7, 70, 39)]
        result = flat_label(result, original, rects[0], text, 20, (20, 23))
    elif name in ('tab_btn_change_back.png', 'positionchange_back.png'):
        text = '체위 변경'
        rects = [(565, 150, 716, 198)]
        a = np.array(original)
        # The original diamond pattern repeats every 151px. Copy the matching
        # clean tile on the same scanline, preserving the vertical gradient.
        a[150:198, 565:716] = a[150:198, 716:867]
        result = Image.fromarray(a)
        result = clip_region(result, paste_effect(result,
            mask_text(original.size, text, 26, (640.5, 174)), 'popup'), rects[0])
    else:
        return None
    return result, rects, text


def build(source, target, start_id):
    rows = []
    cache = {}
    paths = []
    for folder in ['main/action_menu', 'main/h_button', 'main/sozai_bar']:
        paths.extend((source/'cgsys'/folder).glob('*.png'))
    paths.append(source/'cgsys/select/positionchange_back.png')
    for path in sorted(paths):
        relative = path.relative_to(source).as_posix()
        original = Image.open(path).convert('RGBA')
        key = (original.size, hashlib.sha256(original.tobytes()).hexdigest())
        reused = cache.get(key)
        rendered = reused[1] if reused else render(original, relative)
        if rendered is None:
            continue
        result, rects, text = rendered
        save(source, target, rows, start_id, relative, original, result, rects, text)
        rows[-1]['original_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        rows[-1]['reused_from'] = reused[0] if reused else None
        if not reused:
            cache[key] = (rows[-1]['id'], rendered)
    if len(rows) != 151:
        raise ValueError(f'Unexpected endless image inventory: {len(rows)}')
    return rows
