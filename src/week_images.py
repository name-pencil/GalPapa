"""Translate the shared 1/2/3-week duration sprites used by job/status dialogs."""
import hashlib
from PIL import Image
from restaurant_images import draw

def build(source,target,start_id):
 rows=[]
 for number in [1,2,3]:
  relative=f'cgsys/main/number/week/tip_week0{number}.png'
  original=Image.open(source/relative).convert('RGBA');assert original.size==(59,23)
  # Preserve the original numeral. Both callers leave >=107px to the panel edge.
  result=Image.new('RGBA',(90,23));result.paste(original.crop((0,0,14,23)),(0,0))
  result=draw(result,(14,0,90,23),'주 동안',22,left=17,outline=2,stroke_color=(38,0,30,255))
  assert result.crop((0,0,14,23)).tobytes()==original.crop((0,0,14,23)).tobytes()
  dest=target/relative;dest.parent.mkdir(parents=True,exist_ok=True);result.save(dest)
  rows.append(dict(id=start_id+len(rows),path=relative,text=f'{number}주 동안',font_size=22,sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),reused_from=None))
 return rows
