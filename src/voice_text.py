"""Validate and load the separate endless dialogue table against original YBNs."""
from pathlib import Path
import hashlib
import json
import re
import struct

from yuris import args, split_ybn

NAME = 'voice_text_ko.jsonl'
TABLES = {'yst00111': 463, 'yst00112': 426, 'yst00113': 360}
VOICE = re.compile(r'(?:KOH|MIO|YUI|XXX)_[a-z]{4}_[0-9]{12}_[0-9]{2}')
SPEAKERS = {'こはる': '코하루', 'ミオ': '미오', '唯依菜': '유이나'}


def inventory(archives):
    """Only assignment RHS atoms are dialogue; never scan immediate values."""
    result = {}
    for script, count in TABLES.items():
        parts = split_ybn(archives['ysbin\\' + script + '.ybn'][0])
        arguments = list(args(parts))
        commands = bytes((54, 2, 0, 0)) * count + bytes.fromhex('4d0000000e000000')
        if parts[0] != commands or len(arguments) != count * 2:
            raise ValueError('Voice table assignment structure changed: ' + script)
        for command in range(count):
            index, kind, _, payload = arguments[command * 2 + 1]
            size = int.from_bytes(payload[1:3], 'little')
            if (kind != 196608 or payload[:1] != b'M' or size < 2
                    or len(payload) != size + 3 or payload[3:4] != b'"'
                    or payload[-1:] != b'"'):
                raise ValueError(f'Malformed voice atom: {script}:{index}')
            source = payload[4:-1].decode('cp932')
            prefix = VOICE.match(source)
            if not prefix or len(source) == prefix.end():
                raise ValueError(f'Invalid original voice prefix: {script}:{index}')
            rid = f'{script}:a{index:05d}:m00000'
            result[rid] = dict(id=rid, script=script, source_file='ysbin\\' + script + '.ybn',
                command=command, source_line=struct.unpack_from('<I', parts[3], command*4)[0], argument=index, opcode=54,
                argument_kind=kind, payload_sha256=hashlib.sha256(payload).hexdigest(),
                atom_offset=0, macro=None, category='literal', source=source,
                speaker=None, message_group=None)
    return result


def load(path, archives):
    path = Path(path)
    original = inventory(archives)
    seen = set()
    rows = []
    # Missing files must stop a build rather than silently ship Japanese text.
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        def fail(message):
            raise ValueError(f'{path.name}:{number}: {message}')
        try:
            supplied = json.loads(line)
        except json.JSONDecodeError as error:
            fail('invalid JSON: ' + str(error))
        if not isinstance(supplied, dict) or not isinstance(supplied.get('id'), str):
            fail('expected a translation row with a string id')
        rid, target = supplied['id'], supplied.get('target')
        if rid in seen:
            fail('duplicate id ' + rid)
        if rid not in original:
            fail('unknown voice atom ' + rid)
        if not isinstance(target, str) or not target or any(ord(c) < 32 for c in target):
            fail('empty text or unexpected control character: ' + rid)
        row = original[rid]
        for key, value in row.items():
            if key not in supplied or supplied[key] != value:
                fail('source metadata changed (' + key + '): ' + rid)
        source = row['source']
        prefix = VOICE.match(source).group()
        translated_prefix = VOICE.match(target)
        if not translated_prefix or translated_prefix.group() != prefix:
            fail('voice id prefix changed: ' + rid)
        if target[len(prefix):len(prefix)+1].isascii():
            fail('unexpected bytes after voice id: ' + rid)
        speakers = re.findall('【(.*?)】', source)
        if re.findall('【(.*?)】', target) != [SPEAKERS[s] for s in speakers]:
            fail('speaker changed: ' + rid)
        # Preserve delimiter order and the heart glyph placeholder separately.
        if re.findall('[【】「」]', source) != re.findall('[【】「」]', target):
            fail('dialogue delimiters changed: ' + rid)
        if source.count('▼') != target.count('▼'):
            fail('heart placeholder count changed: ' + rid)
        rows.append(dict(row, target=target))
        seen.add(rid)
    missing = original.keys() - seen
    if missing:
        raise ValueError(f'{path.name}: missing {len(missing)} voice rows: {sorted(missing)[:3]}')
    return rows


def refresh_after_restore(patched_files, archives):
    """Refresh immutable dialogue tables after shared save data is restored.

    Append a copy of es.GSD.REFLECT with three definition calls before RET,
    and redirect only its existing label. Original command/argument indices
    remain intact for saves and other labels; no saved file is modified.
    """
    import struct
    from yuris import build_ybn
    name = 'ysbin\\yst00012.ybn'
    base = patched_files.get(name, archives[name][0])
    parts = split_ybn(base)
    original = split_ybn(archives[name][0])
    start, stop = 723, 734
    commands = parts[0]
    expected = bytes.fromhex('2c0201002c0201002d0300002c0a090031000000670200005b0100005b0100002c010000360200002c0100004d000000')
    if original[0][start*4:(stop+1)*4] != expected:
        raise ValueError('Shared-data restore routine changed')
    destination = len(commands) // 4
    arg_start = sum(commands[i+1] for i in range(0, start*4, 4))
    arg_stop = arg_start + sum(commands[i+1] for i in range(start*4, stop*4, 4))
    copied_args = bytearray(parts[1][arg_start*12:arg_stop*12])
    for offset in range(0, len(copied_args), 12):
        kind, value, pool_offset = struct.unpack_from('<III', copied_args, offset)
        if kind == 0 and value:
            if not start <= value <= stop:
                raise ValueError('Restore routine has external branch')
            struct.pack_into('<I', copied_args, offset+4, destination + value-start)
    pool = bytearray(parts[2])
    tail = bytearray(commands[start*4:stop*4])
    lines = bytearray(parts[3][start*4:stop*4])
    for number in (1, 2, 3):
        text = f'CG_VOICETEXT_0{number}.DEFINE'.encode('ascii')
        atom = b'M' + struct.pack('<H', len(text)+2) + b'"' + text + b'"'
        copied_args.extend(struct.pack('<III', 196608, len(atom), len(pool)))
        pool.extend(atom)
        tail.extend(bytes.fromhex('2c010000'))
        lines.extend(parts[3][stop*4:(stop+1)*4])
    tail.extend(bytes.fromhex('4d000000'))
    lines.extend(parts[3][stop*4:(stop+1)*4])
    output = bytearray(build_ybn(base, [commands+tail, parts[1]+copied_args,
                                          bytes(pool), parts[3]+lines]))
    struct.pack_into('<I', output, 8, (len(commands)+len(tail))//4)
    patched_files[name] = bytes(output)
    label_name = 'ysbin\\ysl.ybn'
    labels = bytearray(patched_files.get(label_name, archives[label_name][0]))
    marker = b'es.GSD.REFLECT'
    position = labels.find(marker)
    if position < 0 or labels.find(marker, position+1) != -1:
        raise ValueError('Restore label missing or ambiguous')
    target = position + len(marker) + 4  # name, hash, command, script
    if struct.unpack_from('<II', labels, target) != (start, 12):
        raise ValueError('Restore label target changed')
    struct.pack_into('<I', labels, target, destination)
    patched_files[label_name] = bytes(labels)
    return dict(script=name, original_entry=start, refreshed_entry=destination,
                definitions=3, original_indices_preserved=True)
