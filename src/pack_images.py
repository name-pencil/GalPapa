"""YPF replacement packer: append payloads; preserve all other entries."""
from pathlib import Path
import struct,shutil,hashlib
from archive_index import index,SWAP
from config_images import murmur2

def digest(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def pack(original,output,replacements):
 original=Path(original);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
 with original.open('rb') as f:
  header=f.read(32);end=struct.unpack_from('<I',header,12)[0];table=bytearray(f.read(end-32))
 shutil.copyfile(original,output);pos=0;changed=set()
 with original.open('rb') as source,output.open('r+b') as target:
  for _ in range(struct.unpack_from('<I',header,8)[0]):
   length=SWAP.get(table[pos+4]^255,table[pos+4]^255);pos+=5
   name=bytes(x^255 for x in table[pos:pos+length]).decode('cp932');pos+=length
   if name in replacements:
    kind,compressed,size,packed,offset,checksum=struct.unpack_from('<BBIIQI',table,pos)
    assert compressed==0 and size==packed
    source.seek(offset);assert murmur2(source.read(packed))==checksum,name
    raw=Path(replacements[name]).read_bytes();target.seek(0,2);offset=target.tell();target.write(raw)
    struct.pack_into('<BBIIQI',table,pos,kind,0,len(raw),len(raw),offset,murmur2(raw));changed.add(name)
   pos+=22
  assert changed==replacements.keys()
  target.seek(32);target.write(table)
 old={e['name']:e for e in index(original)}
 with output.open('rb') as stream:
  for entry in index(output):
   if entry['name'] in replacements:
    stream.seek(entry['offset']);assert stream.read(entry['packed'])==Path(replacements[entry['name']]).read_bytes()
   else:assert entry==old[entry['name']]
 return {'sha256':digest(output),'replaced_entries':len(changed),'preserved_entries':len(old)-len(changed)}
