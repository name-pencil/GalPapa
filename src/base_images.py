"""Maplestory main-menu lettering and Korean common-menu image labels.

Includes the existing config image patch; never rewrites story translations.
"""
from pathlib import Path
import collections
import hashlib
import json
import struct
import shutil
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config_images import murmur2, replace_label
from archive_index import index, SWAP
from popup_text import MESSAGE_DIALOGS, POPUPS, render_popup, lettering, render_caution, CAUTION
from app_ui_text import make_app_images

from paths import ROOT, SOURCE_ROOT
SOURCE = None  # Assigned by images.build.
OUT = None  # Disposable output selected by images.build.
MAPLE = ROOT / 'assets/fonts/Maplestory Bold.ttf'
PAPER = ROOT / 'assets/fonts/Paperlogy-6SemiBold.ttf'
TITLE = {
    'start': '처음부터', 'load': '이어서', 'extra': '엑스트라',
    'config': '환경 설정', 'exit': '게임 종료', 'story': '스토리',
    'endless': '엔드리스 파파카츠 모드', 'allflg': '업적 해제', 'back': '돌아가기',
}
BUTTONS = {
    'backlog/btn_back': '돌아가기',
    'saveload/btn_back': '돌아가기',
    'saveload/saveload_btn_title': '타이틀',
    'saveload/saveload_bt_exit': '게임 종료',
    'saveload/saveload_bt_toload': '불러오기',
    'saveload/saveload_bt_tosave': '저장',
    'extra/btn_back': '돌아가기', 'extra/btn_end': '게임 종료',
    'extra/btn_title': '타이틀', 'extra/btn_tab_cgmode': 'CG 모드',
    'extra/btn_tab_rpmode': '장면 회상',
    'confirm/btn_back': '닫기', 'confirm/btn_no': '아니요', 'confirm/btn_yes': '예',
}
DIALOGS = {
    'allflg': '조건과 관계없이 모든 업적을 해제합니다.\n정말 진행하시겠습니까?',
    'cfginit': '설정을 초기화하시겠습니까?', 'cfginit_end': '설정을 초기화했습니다.',
    'end': '게임을 종료하시겠습니까?', 'load': '불러오시겠습니까?',
    'qload': '빠른 불러오기를 실행하시겠습니까?', 'qload_end': '빠른 불러오기를 완료했습니다.',
    'qsave': '빠른 저장을 하시겠습니까?', 'rpmode': '회상을 종료하시겠습니까?',
    'save': '저장하시겠습니까?', 'save_delete': '저장 데이터를 삭제하시겠습니까?',
    'save_ow': '덮어쓰시겠습니까?', 'title': '타이틀로 돌아가시겠습니까?',
}
DIALOGS.update(MESSAGE_DIALOGS)


PROGRESS_CALLBACK = None

def save_asset(image, relative, target, category, extra=None):
    path = OUT / 'images' / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    if PROGRESS_CALLBACK: PROGRESS_CALLBACK(relative)
    return {**(extra or {}), 'file': relative, 'target': target, 'category': category}


def title_asset(path, text):
    source = Image.open(path).convert('RGBA')
    original = np.array(source)
    # English starts to the right of x=338 in every title button. Preserve that
    # region pixel-for-pixel, including its existing hover glow and disabled alpha.
    rect = (38, 5, 338, 61)
    cleaned = original.copy()
    for y in range(rect[1], rect[3]):
        cleaned[y, rect[0]:rect[2]] = original[y, 25]
    scale = 4
    size = 32
    while True:
        font = ImageFont.truetype(str(MAPLE), size * scale)
        bounds = font.getbbox(text)
        if (bounds[2] - bounds[0]) / scale <= 264:
            break
        size -= 1
        if size < 18:
            raise ValueError('Title too long: ' + text)
    layer = Image.new('RGBA', (300 * scale, 56 * scale))
    draw = ImageDraw.Draw(layer)
    x = 15 * scale - bounds[0]
    y = (56 * scale - (bounds[3] - bounds[1])) // 2 - bounds[1]
    hover = path.stem.endswith('_over')
    if hover:
        glow_mask = Image.new('L', layer.size)
        ImageDraw.Draw(glow_mask).text((x, y), text, font=font, fill=225,
                                      stroke_width=4 * scale, stroke_fill=225)
        glow_mask = glow_mask.filter(ImageFilter.GaussianBlur(2.5 * scale))
        glow = Image.new('RGBA', layer.size, (255, 48, 155, 0))
        glow.putalpha(glow_mask)
        layer.alpha_composite(glow)
    draw = ImageDraw.Draw(layer)
    draw.text((x + scale, y + scale), text, font=font, fill=(53, 7, 35, 255),
              stroke_width=4 * scale, stroke_fill=(53, 7, 35, 255))
    draw.text((x, y), text, font=font, fill=(242, 46, 140, 255) if hover else (202, 42, 120, 255),
              stroke_width=3 * scale, stroke_fill='white')
    layer = layer.resize((300, 56), Image.Resampling.LANCZOS)
    coverage = layer.getchannel('A')
    layer.putalpha(source.getchannel('A').getextrema()[1])
    result = Image.fromarray(cleaned, 'RGBA')
    result.paste(layer, (rect[0], rect[1]), coverage)
    result_pixels = np.array(result)
    assert np.array_equal(result_pixels[:, 338:], original[:, 338:]), 'English region changed'
    assert np.array_equal(result_pixels[:, :38], original[:, :38]), 'Left button edge changed'
    assert np.array_equal(result_pixels[:5], original[:5]), 'Top button edge changed'
    assert np.array_equal(result_pixels[61:], original[61:]), 'Bottom button edge changed'
    return result, dict(font=MAPLE.name, font_size=size, preserved_english_from_x=338)


def dialog_asset(path, text):
    source = Image.open(path).convert('RGBA')
    pixels = np.array(source)
    reference = np.array(Image.open(SOURCE / 'confirm/dialog_save.png').convert('RGBA'))
    # All common confirmations share this background. Reuse clean areas from
    # the original artwork; the diamond pattern repeats at approximately 151 px.
    clean = reference.copy()
    for x in range(260, 505):
        donor = x - 302 if x >= 302 else x + 302
        clean[35:110, x] = reference[35:110, donor]
    white = pixels[25:115, :, :3].min(axis=2) > 180
    yy, xx = np.where(white)
    assert len(xx)
    x0, y0, x1, y1 = max(0, int(xx.min()) - 8), int(yy.min()) + 17, min(source.width, int(xx.max()) + 9), int(yy.max()) + 34
    result_pixels = pixels.copy()
    result_pixels[y0:y1, x0:x1] = clean[y0:y1, x0:x1]
    result = Image.fromarray(result_pixels, 'RGBA')
    layer = lettering((source.width, 120), text.splitlines(), center=(None, 72), glow=True)
    result.alpha_composite(layer)
    assert np.array_equal(np.array(result)[120:], pixels[120:]), 'Dialog lower artwork changed'
    return result


def make_images():
    records = []
    for key, text in TITLE.items():
        for path in sorted((SOURCE / 'title').glob('title_' + key + '_*.png')):
            image, meta = title_asset(path, text)
            records.append(save_asset(image, 'title/' + path.name, text, 'maple_title', meta))
    for prefix, text in BUTTONS.items():
        folder, stem = prefix.split('/')
        for path in sorted((SOURCE / folder).glob(stem + '_*.png')):
            image = Image.open(path).convert('RGBA')
            if image.getchannel('A').getextrema()[1] == 0:
                continue
            pad = 15 if image.height >= 45 else 7
            dominant = collections.Counter(map(tuple, np.array(image).reshape(-1, 4))).most_common(1)[0][0]
            # Common-menu pressed states use the same flat purple glow as hover
            # states, unlike config's bright-pink selected-state gradient.
            flat_glow = 70 < dominant[0] < 200 and dominant[1] < 70 and dominant[2] > 50
            cleanup_name = path.stem + '_over.png' if flat_glow else path.name
            image, meta = replace_label(image, (10, pad, image.width - 10, image.height - pad), text,
                                        button=True, filename=cleanup_name)
            records.append(save_asset(image, folder + '/' + path.name, text, 'common_button', meta))
    for key, text in DIALOGS.items():
        path = SOURCE / 'confirm' / ('dialog_' + key + '.png')
        records.append(save_asset(dialog_asset(path, text), 'confirm/' + path.name, text, 'common_dialog'))
    for key, specs in POPUPS.items():
        image = render_popup(key)
        records.append(save_asset(image, 'confirm/dialog_' + key + '.png', '\n'.join(s['text'] for s in specs),
                                  'guide_and_job_popup', {'text_blocks': specs, 'body_glow': False}))
    caution = render_caution()
    caution.save(OUT / 'caution.png')
    for relative, image, text, meta in make_app_images():
        records.append(save_asset(image, relative, text, 'app_white_ui', meta))
    return records
