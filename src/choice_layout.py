"""Center translated choices using measured Korean text widths.

Keep the original text areas, button coordinates, glyph size and VM commands.
Only the three existing horizontal-centering expressions are replaced. Unknown
strings retain the original calculation; translated literals use the width table.
"""
from pathlib import Path
import hashlib,json,struct,zlib
from PIL import ImageFont
from paths import ROOT
from yuris import read_archive,split_ybn,build_ybn,args

TEXT=bytes.fromhex('56030024f00a48030040300029010000')
CENTER=bytes.fromhex('480300402a0b420100022f0000')
LENGTH=bytes.fromhex('560300403c004201000129010000')
END=bytes.fromhex('420100022f00002d0000')
MEASURE_EM=24

def literal(raw):return b'M'+struct.pack('<H',len(raw)+2)+b'"'+raw+b'"'
def integer(value):return b'W\x02\x00'+struct.pack('<h',value)

def build(input_archive,out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 chars=(out.parent/'text/hangul_map.bin').read_bytes().decode('utf-16le');mapping={c:chr(0xe000+i) for i,c in enumerate(chars)}
 def encode(text):return ''.join(mapping.get(c,c) for c in text).encode('cp932')
 rows=[json.loads(l) for l in (ROOT/'translation/reviewd/ui_literals_ko.jsonl').read_text(encoding='utf-8').splitlines()]
 font=ImageFont.truetype(str(ROOT/'assets/fonts/Paperlogy-6SemiBold.ttf'),MEASURE_EM)
 texts=sorted({r['target'] for r in rows if r.get('macro')=='ES.SEL.SET'})
 widths={text:round(font.getlength(text)) for text in texts}
 correction=bytearray()
 for text,width in widths.items():
  delta=width-len(text)*26
  if delta:correction.extend(TEXT+literal(encode(text))+b'=\0\0'+integer(delta)+b'*\0\0+\0\0')
 raw=Path(input_archive).read_bytes();archive=read_archive(input_archive)
 name='ysbin\\yst00023.ybn';original,entry=archive[name];parts=split_ybn(original);before=list(args(parts));edits={}
 for number,variable in [(584,2817),(588,2825),(592,2833)]:
  nominal=LENGTH+b'H\x03\x00@'+struct.pack('<H',variable)+b'*\0\0'
  assert before[number][3]==CENTER+nominal+END,number
  # All three unchanged SEL font definitions are 26px.
  edits[number]=CENTER+nominal+bytes(correction)+END
 table=bytearray(parts[1]);pool=bytearray(parts[2])
 for number,replacement in edits.items():
  struct.pack_into('<II',table,number*12+4,len(replacement),len(pool));pool.extend(replacement)
 patched=build_ybn(original,[parts[0],bytes(table),bytes(pool),parts[3]]);after=split_ybn(patched)
 assert after[0]==parts[0] and after[3]==parts[3]
 for number,kind,offset,payload in args(after):
  if number in edits:assert payload==edits[number]
  else:assert after[1][number*12:number*12+12]==parts[1][number*12:number*12+12],number
 assert after[2][:len(parts[2])]==parts[2]
 rebuilt=bytearray(raw);end=struct.unpack_from('<I',rebuilt,12)[0];pos=rebuilt.find(entry,32,end);assert pos>=32
 packed=zlib.compress(patched,9);struct.pack_into('<BBIIQ',rebuilt,pos+len(entry)-22,0,1,len(patched),len(packed),len(rebuilt));rebuilt.extend(packed)
 output=out/'update2.ypf';output.write_bytes(rebuilt)
 for key,(payload,_) in read_archive(output).items():assert payload==(patched if key==name else archive[key][0]),key
 assert max(widths.values())+32<700
 report=dict(script=name,arguments=list(edits),alignment='measured text centered in original text surface',font_size_unchanged=26,measurement_em=MEASURE_EM,unique_translated_choices=len(texts),max_width=max(widths.values()),commands_and_branches_unchanged=True,archive_sha256=hashlib.sha256(rebuilt).hexdigest(),widths=widths,runtime_verification='pending')
 (out/'manifest.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8');return report
