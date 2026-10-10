"""Apply 25px only to dialogue glyphs and advances."""
from pathlib import Path
import hashlib,json,struct,zlib
from yuris import read_archive,split_ybn,build_ybn,args

def build(input_archive,out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 raw=Path(input_archive).read_bytes();archive=read_archive(input_archive)
 name='ysbin\\yst00087.ybn';original,entry=archive[name];parts=split_ybn(original);before=list(args(parts))
 width=bytes.fromhex('480300405713');height=bytes.fromhex('480300405813');half=bytes.fromhex('420100022f0000')
 scale=bytes.fromhex('420100192a00004201000b2b0000420100172f0000')
 edits={2128:(width+half,width+scale+half),2133:(width,width+scale),2135:(width,width+scale),2137:(height,height+scale)}
 table=bytearray(parts[1]);pool=bytearray(parts[2])
 for number,(expected,replacement) in edits.items():
  assert before[number][1]==0x10000 and before[number][3]==expected,number
  struct.pack_into('<II',table,number*12+4,len(replacement),len(pool));pool.extend(replacement)
 patched=build_ybn(original,[parts[0],bytes(table),bytes(pool),parts[3]])
 after=split_ybn(patched)
 for number,kind,offset,payload in args(after):
  if number in edits:assert payload==edits[number][1],number
  else:assert after[1][number*12:number*12+12]==parts[1][number*12:number*12+12],number
 rebuilt=bytearray(raw);end=struct.unpack_from('<I',rebuilt,12)[0];pos=rebuilt.find(entry,32,end);assert pos>=32
 packed=zlib.compress(patched,9);struct.pack_into('<BBIIQ',rebuilt,pos+len(entry)-22,0,1,len(patched),len(packed),len(rebuilt));rebuilt.extend(packed)
 output=out/'update2.ypf';output.write_bytes(rebuilt)
 for key,(payload,_) in read_archive(output).items():assert payload==(patched if key==name else archive[key][0]),key
 report=dict(scale=25/23,normal_body_size_before=23,normal_body_size_after=25,changed_arguments=list(edits),source_sha256=hashlib.sha256(raw).hexdigest(),archive_sha256=hashlib.sha256(rebuilt).hexdigest(),unchanged_archive_entries=len(archive)-1,installed=False,runtime_verification='pending')
 (out/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8');return report

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);a=p.parse_args();print(json.dumps(build(a.input,a.out),indent=2))
