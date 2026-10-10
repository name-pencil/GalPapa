"""Deterministic, user-approved font replacement of plain config image labels."""
from pathlib import Path
import collections
import hashlib
import json
import struct
import zlib
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from archive_index import index, SWAP

from paths import ROOT, SOURCE_ROOT
SOURCE = None  # Assigned to freshly extracted originals by images.build.
OUT = None  # Disposable output selected by images.build.
FONT = ROOT / 'assets/fonts/Paperlogy-6SemiBold.ttf'
MEDIUM = ROOT / 'assets/fonts/Paperlogy-5Medium.ttf'

BACKGROUNDS = {
    'back_system.png': [
        (55, 129, 540, '창 모드'),
        (55, 187, 540, '비활성 상태에서도 실행'),
        (55, 245, 540, '항상 맨 위에 표시'),
        (55, 303, 540, '읽지 않은 문장도 스킵'),
        (675, 129, 275, '자동 진행 속도'),
        (675, 187, 275, '메시지 창 불투명도'),
        (675, 245, 215, '글자 테두리'),
        (925, 245, 72, '그림자'),
    ],
    'back_sound.png': [
        (55, 129, 250, '전체 음량'),
        (55, 187, 250, '음성'),
        (55, 303, 250, '음성 재생 시 BGM 감소율'),
        (55, 361, 250, '효과음 음량'),
        (55, 419, 250, 'BGV 음량'),
        (55, 477, 250, '시스템 효과음 음량'),
        (55, 535, 250, '음성 중단 시점'),
        (55, 593, 250, '자동 진행 시 음성 재생 대기'),
    ],
    'back_dialog.png': [
        (55, 129, 540, '저장 시 확인'),
        (55, 187, 540, '불러오기 시 확인'),
        (55, 245, 540, '빠른 저장 시 확인'),
        (55, 303, 540, '빠른 불러오기 시 확인'),
        (55, 361, 540, '저장 데이터 덮어쓰기 시 확인'),
        (55, 419, 540, '타이틀로 돌아갈 때 확인'),
        (55, 477, 540, '게임 종료 시 확인'),
        (675, 129, 540, '호감도 힌트 표시'),
    ],
}
BUTTONS = {
    'btn_window': '창 모드', 'btn_fullscreen': '전체 화면',
    'btn_nexttext': '다음 문장', 'btn_nextvoice': '다음 음성',
    'btn_default': '설정 초기화', 'btn_exit': '게임 종료',
    'btn_title': '타이틀', 'btn_back': '돌아가기',
    'btn_rpmode': '회상 선택으로', 'btn_tab_system': '시스템',
    'btn_tab_sound': '사운드', 'btn_tab_dialog': '기타',
    'btn_voice': '음성 테스트',
}


def murmur2(data):
    """YPF v495 uncompressed-payload checksum: MurmurHash2, seed zero."""
    h, position = len(data), 0
    while position + 4 <= len(data):
        k = struct.unpack_from('<I', data, position)[0]
        k = (k * 0x5bd1e995) & 0xffffffff
        k ^= k >> 24
        k = (k * 0x5bd1e995) & 0xffffffff
        h = ((h * 0x5bd1e995) ^ k) & 0xffffffff
        position += 4
    tail = data[position:]
    if tail:
        h ^= int.from_bytes(tail, 'little')
        h = (h * 0x5bd1e995) & 0xffffffff
    h ^= h >> 13
    h = (h * 0x5bd1e995) & 0xffffffff
    return h ^ (h >> 15)


def render_text(text, max_width, size, color, shadow):
    font_path = MEDIUM if shadow else FONT
    while True:
        font = ImageFont.truetype(str(font_path), size * 4)
        bbox = font.getbbox(text)
        if (bbox[2] - bbox[0]) / 4 <= max_width or size <= 12:
            break
        size -= 1
    width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    layer = Image.new('RGBA', (width + 24, height + 24))
    draw = ImageDraw.Draw(layer)
    if shadow:
        draw.text((12 - bbox[0] + 4, 12 - bbox[1] + 4), text, font=font,
                  fill=(0, 0, 0, 210), stroke_width=2, stroke_fill=(0, 0, 0, 160))
    draw.text((12 - bbox[0], 12 - bbox[1]), text, font=font, fill=color)
    layer = layer.resize(((width + 24 + 3) // 4, (height + 24 + 3) // 4), Image.Resampling.LANCZOS)
    return layer, size


def replace_label(image, region, text, *, button=False, filename=''):
    pixels = np.array(image)
    x0, y0, x1, y1 = region
    crop = pixels[y0:y1, x0:x1]
    bright = crop[:, :, :3].min(axis=2) > (180 if button else 95)
    bright &= crop[:, :, 3] > (0 if button else 120)
    yy, xx = np.where(bright)
    if not len(xx):
        raise ValueError('No source text detected: ' + text)
    glyph_bounds = (x0 + int(xx.min()), y0 + int(yy.min()), x0 + int(xx.max()) + 1, y0 + int(yy.max()) + 1)
    mask = np.zeros(pixels.shape[:2], dtype=np.uint8)
    pad = 6 if button and filename.endswith('_over.png') and image.height >= 45 else (2 if button else 4)
    gx0, gy0, gx1, gy1 = glyph_bounds
    mask[max(0, gy0-pad):min(image.height, gy1+pad), max(0, gx0-pad):min(image.width, gx1+pad)] = 255
    # Keep original antialiasing, transparency, decoration and background outside
    # the narrowly dilated old glyph mask. Inpainting restores only erased ink.
    if button:
        restored = pixels.copy()
        for row in np.where(mask.any(axis=1))[0]:
            candidates = pixels[row, 12:-12]
            candidates = candidates[candidates[:, :3].min(axis=1) < 100]
            if not len(candidates):
                raise ValueError('No clean button background pixels: ' + filename)
            if filename.endswith('_over.png') and image.height >= 45:
                background = collections.Counter(map(tuple, pixels.reshape(-1, 4))).most_common(1)[0][0]
            else:
                background = collections.Counter(map(tuple, candidates)).most_common(1)[0][0]
            restored[row, mask[row] > 0] = background
        cleaned = Image.fromarray(restored, 'RGBA')
    else:
        rgb = cv2.inpaint(pixels[:, :, :3], mask, 5, cv2.INPAINT_NS)
        alpha = cv2.inpaint(pixels[:, :, 3], mask, 5, cv2.INPAINT_NS)
        cleaned = Image.fromarray(np.dstack([rgb, alpha]), 'RGBA')
    if button:
        color = tuple(int(v) for v in crop[yy, xx][np.argmax(crop[yy, xx, :3].min(axis=1))])
        max_width = image.width - 20
        size = 18 if image.height >= 45 else 16
    else:
        color, max_width, size = (255, 255, 255, 255), x1 - x0 - 4, 18
    render_color = color[:3] + (255,) if button else color
    layer, size = render_text(text, max_width, size, render_color, not button)
    if button:
        left = (image.width - layer.width) // 2
    else:
        left = x0 - 3
    center = (glyph_bounds[1] + glyph_bounds[3]) / 2
    top = round(center - layer.height / 2)
    if button:
        coverage = layer.getchannel('A')
        layer.putalpha(color[3])
        cleaned.paste(layer, (left, top), coverage)
    else:
        cleaned.alpha_composite(layer, (left, top))
    allowed = mask > 0
    allowed[top:top + layer.height, left:left + layer.width] = True
    changed = np.any(np.array(cleaned) != pixels, axis=2)
    assert not np.any(changed & ~allowed), 'Non-text pixels changed'
    return cleaned, dict(target=text, source_bounds=glyph_bounds, font_size=size,
                         changed_pixels=int(changed.sum()))


def build_images():
    records = []
    for name, labels in BACKGROUNDS.items():
        image = Image.open(SOURCE / name).convert('RGBA')
        edits = []
        for x, cy, width, text in labels:
            image, edit = replace_label(image, (x, cy - 13, x + width, cy + 12), text)
            edits.append(edit)
        image.save(OUT / 'images' / name)
        records.append(dict(file=name, edits=edits))
    for prefix, text in BUTTONS.items():
        for path in sorted(SOURCE.glob(prefix + '_*.png')):
            image = Image.open(path).convert('RGBA')
            pad_y = 15 if image.height >= 45 else 7
            image, edit = replace_label(image, (10, pad_y, image.width - 10, image.height - pad_y), text, button=True, filename=path.name)
            image.save(OUT / 'images' / path.name)
            records.append(dict(file=path.name, edits=[edit]))
    return records
