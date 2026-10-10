"""Build and verify the supplied translations without rewriting their text.

Called by the installer pipeline with original archive and temporary output.
"""
from pathlib import Path
import argparse
import collections
import datetime
import hashlib
import json
import shutil
import subprocess
from yuris import ROOT, read_archive, split_ybn, build_ybn, args, struct, zlib


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def build(archive, out, messages_only=False, progress=None):
    from types import SimpleNamespace
    from paths import SOURCE_ROOT
    options=SimpleNamespace(archive=archive,out=out,messages_only=messages_only)
    source = ROOT / 'translation'
    stage = Path(options.out)
    if options.messages_only:
        stage = stage / 'messages_only'
    stage.mkdir(exist_ok=True, parents=True)
    archive_path = Path(options.archive).resolve()
    baseline = json.loads((SOURCE_ROOT / 'original_hashes.json').read_text(encoding='utf-8'))
    for name in ['update1.ypf', 'ysbin.ypf']:
        require(sha(archive_path.with_name(name).read_bytes()) == baseline[name], 'Source archive changed: ' + name)
    archives = read_archive(archive_path)
    grouped = collections.defaultdict(lambda: collections.defaultdict(list))
    counts = {}
    input_hashes = {}
    all_rows = []
    skipped_branch_references = []
    script_arguments = {}
    for filename, category in [('messages_ko.jsonl', 'message'), ('ui_literals_ko.jsonl', 'literal')]:
        if options.messages_only and category == 'literal':
            continue
        path = source / 'reviewd' / filename
        raw = path.read_bytes()
        rows = [json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
        require(len({r['id'] for r in rows}) == len(rows), 'Duplicate IDs: ' + filename)
        counts[category] = len(rows)
        input_hashes[filename] = sha(raw)
        if category == 'literal':
            # Opcode 45, kind 0 stores an immediate branch destination in
            # the second DWORD, NOT a payload length. Extraction incorrectly
            # scanned this value as a string length and produced false aliases.
            real_atoms = {}
            for row in rows:
                name = 'ysbin\\' + row['script'] + '.ybn'
                if name not in script_arguments:
                    script_arguments[name] = list(args(split_ybn(archives[name][0])))
                if row['argument_kind'] != 0:
                    position = script_arguments[name][row['argument']][2] + row['atom_offset']
                    key = (name, position)
                    if key in real_atoms:
                        require(real_atoms[key]['target'] == row['target'], 'Conflicting UI translations')
                    real_atoms[key] = row
            accepted = []
            for row in rows:
                if row['argument_kind'] == 0:
                    require(row['opcode'] == 45, 'Unrecognized literal immediate: ' + row['id'])
                    name = 'ysbin\\' + row['script'] + '.ybn'
                    position = script_arguments[name][row['argument']][2] + row['atom_offset']
                    actual = real_atoms.get((name, position))
                    require(actual is not None and actual['source'] == row['source']
                            and actual['target'] == row['target'], 'Unresolved false UI reference: ' + row['id'])
                    skipped_branch_references.append(dict(id=row['id'], actual_id=actual['id']))
                else:
                    accepted.append(row)
            rows = accepted
            counts['literal_applied'] = len(rows)
        for row in rows:
            require(isinstance(row['target'], str) and bool(row['target']), 'Empty target: ' + row['id'])
            require(not any(ord(c) < 32 for c in row['target']), 'Unexpected control character: ' + row['id'])
            grouped['ysbin\\' + row['script'] + '.ybn'][row['argument']].append((category, row))
            all_rows.append(row)
    import dialogue_layout
    layout_report = dialogue_layout.prepare(all_rows, archives)
    (stage / 'dialogue_layout_report.json').write_text(json.dumps(layout_report, ensure_ascii=False, indent=2), encoding='utf-8')
    # Preserve initial-release slots for existing save/backlog compatibility.
    from mapping_compat import COMPAT_PREFIX
    old_mapping = COMPAT_PREFIX
    chars = list(old_mapping)
    require(len(set(chars)) == len(chars), 'Duplicate existing mapping')
    chars += sorted({c for r in all_rows for c in r['target'] if ord(c) >= 128} - set(chars))
    require(len(chars) <= 1880, 'CP932 private-use mapping capacity exceeded')
    mapping = {c: chr(0xe000 + i) for i, c in enumerate(chars)}

    def encode(text):
        result = ''.join(mapping.get(c, c) for c in text).encode('cp932')
        decoded = ''.join(chars[ord(c) - 0xe000] if 0xe000 <= ord(c) < 0xe000 + len(chars) else c
                          for c in result.decode('cp932'))
        require(decoded == text, 'Encoding roundtrip failed')
        return result

    patched_files = {}
    changed_args = 0
    inherited_literal_hashes = 0
    for name, targets in grouped.items():
        original = archives[name][0]
        parts = split_ybn(original)
        require(build_ybn(original, parts) == original, 'YBN roundtrip: ' + name)
        original_args = list(args(parts))
        replacements = {}
        expression_args = set()
        command_edits = {}
        for number, edits in targets.items():
            index, kind, offset, payload = original_args[number]
            spans = []
            for category, row in edits:
                require(kind == row['argument_kind'], 'Argument kind: ' + row['id'])
                encoded = encode(row['target'])
                if category == 'message':
                    require(sha(payload) == row['payload_sha256'], 'Payload hash: ' + row['id'])
                    require(len(edits) == 1, 'Overlapping message: ' + row['id'])
                    require(payload.decode('cp932') == row['source'], 'Message source: ' + row['id'])
                    segments = row.get('_layout_lines')
                    if segments:
                        if len(segments) == 1:
                            encoded = encode(segments[0])
                        else:
                            encoded = dialogue_layout.expression(segments, encode)
                            expression_args.add(number)
                            command_edits[row['command']] = 110
                    spans.append((0, len(payload), encoded))
                else:
                    require(sha(payload) == row['payload_sha256'], 'Original literal payload hash: ' + row['id'])
                    pos = row['atom_offset']
                    old = row['source'].encode('cp932')
                    expected = b'M' + struct.pack('<H', len(old) + 2) + b'"' + old + b'"'
                    require(payload[pos:pos + len(expected)] == expected, 'Literal structure: ' + row['id'])
                    require(len(encoded) + 2 <= 65535, 'Literal too long: ' + row['id'])
                    atom = b'M' + struct.pack('<H', len(encoded) + 2) + b'"' + encoded + b'"'
                    spans.append((pos, len(expected), atom))
            cursor = 0
            result = bytearray()
            for pos, length, encoded in sorted(spans):
                require(pos >= cursor, 'Overlapping literal: ' + name)
                result.extend(payload[cursor:pos])
                result.extend(encoded)
                cursor = pos + length
            result.extend(payload[cursor:])
            replacements[number] = bytes(result)
        import dynamic_speaker
        dynamic_speaker.apply(original_args, targets, replacements, expression_args, command_edits, encode, parts[0])
        # Append translated payloads; source arguments may share/overlap storage.
        # Leaving the original pool intact preserves every untargeted reference.
        commands = bytearray(parts[0])
        for command, opcode in command_edits.items():
            require(commands[command*4] == 106 and commands[command*4+1] == 1, 'Expected literal message command')
            commands[command*4] = opcode
        pool = bytearray(parts[2])
        table = bytearray(parts[1])
        stored = {}
        for number, value in replacements.items():
            if value not in stored:
                stored[value] = len(pool)
                pool.extend(value)
            if number in expression_args: struct.pack_into('<I', table, number * 12, 196608)
            struct.pack_into('<II', table, number * 12 + 4, len(value), stored[value])
        patched = build_ybn(original, [bytes(commands), bytes(table), bytes(pool), parts[3]])
        rebuilt_parts = split_ybn(patched)
        require(rebuilt_parts[0] == bytes(commands) and rebuilt_parts[3] == parts[3], 'Command data changed')
        for number, kind, pos, payload in args(rebuilt_parts):
            if number in replacements:
                require(payload == replacements[number], 'Translated argument verification failed')
            else:
                # Some argument records carry immediate values rather than string
                # lengths. Preserve the descriptor and entire source pool verbatim.
                offset = number * 12
                require(table[offset:offset + 12] == parts[1][offset:offset + 12], 'Untargeted descriptor changed')
        require(rebuilt_parts[2][:len(parts[2])] == parts[2], 'Original string pool changed')
        patched_files[name] = patched
        if progress: progress(len(patched_files),len(grouped))
        changed_args += len(replacements)
    # Keep the proven YPF index and append updated streams, as the sample does.
    rebuilt = bytearray(archive_path.read_bytes())
    index_end = struct.unpack_from('<I', rebuilt, 12)[0]
    for name, patched in patched_files.items():
        entry = archives[name][1]
        position = rebuilt.find(entry, 32, index_end)
        require(position >= 32, 'Archive entry not found: ' + name)
        packed = zlib.compress(patched, 9)
        struct.pack_into('<BBIIQ', rebuilt, position + len(entry) - 22,
                         0, 1, len(patched), len(packed), len(rebuilt))
        rebuilt.extend(packed)
    patch_path = stage / 'update2.ypf'
    patch_path.write_bytes(rebuilt)
    mapping_bytes = ''.join(chars).encode('utf-16le')
    (stage / 'hangul_map.bin').write_bytes(mapping_bytes)
    check = read_archive(patch_path)
    require(check.keys() == archives.keys(), 'Archive inventory mismatch')
    for name, (payload, _) in check.items():
        require(payload == patched_files.get(name, archives[name][0]), 'Archive payload mismatch: ' + name)
    report = dict(inputs=input_hashes, rows=counts, changed_scripts=len(patched_files),
                  changed_arguments=changed_args, archive_entries=len(check), characters=len(chars),
                  retained_mapping_characters=len(old_mapping), patch_sha256=sha(bytes(rebuilt)),
                  inherited_literal_hashes=inherited_literal_hashes,
                  preserved_branch_references=len(skipped_branch_references),
                  mapping_sha256=sha(mapping_bytes), structural_verification='passed',
                  runtime_verification='pending', installed=False)
    (stage / 'branch_reference_audit.json').write_text(json.dumps(skipped_branch_references, indent=2), encoding='utf-8')
    (stage / 'manifest.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--messages-only',action='store_true')
    options=parser.parse_args()
    print(json.dumps(build(options.archive,options.out,options.messages_only),indent=2,ensure_ascii=True))
