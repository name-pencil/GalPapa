"""Reflow message groups without changing words, command counts, or branches."""
import collections
import functools
import re
from yuris import args, split_ybn

NEWLINE = bytes.fromhex('560300247f00570200ef0029010000560300247f00570200f000290100002b0000')
NAME = bytes.fromhex('560300248e064201000329010000')
NAME_TOKEN = '【{NAME}】'
EXCEPTIONS = {'yst00435:g0168','yst00443:g0027','yst00496:g0057','yst00535:g0021'}

def width(text):
    # Runtime-selected heroine names: reserve four full-width glyphs plus brackets.
    return sum(12 if ord(c)<128 else 25 for c in text.replace(NAME_TOKEN,'【가나다라】'))

def partition(lines, limit):
    text = ' '.join(s.strip() for s in lines)
    # Word boundaries; retain original punctuation and never split a Korean word.
    spans = list(re.finditer(r'\S+',text))
    tokens = [m.group() for m in spans]
    original = set()
    count = 0
    for line in lines[:-1]:
        count += len(line.split())
        original.add(count)
    prefix = [0]
    for t in tokens: prefix.append(prefix[-1]+width(t))
    def size(a,b): return prefix[b]-prefix[a]+12*(b-a-1)
    for total in range(len(lines),4):
        @functools.lru_cache(None)
        def solve(a,left):
            if left==0:return (0,[]) if a==len(tokens) else None
            best=None
            for b in range(a+1,len(tokens)+1):
                w=size(a,b)
                if w>limit:break
                if len(tokens)-b<left-1:break
                tail=solve(b,left-1)
                if tail is None:continue
                cost=tail[0]
                if b<len(tokens):
                    cost += 0 if b in original else 100
                    if b not in original and not tokens[b-1].endswith(('。','、','.',',','!','?','…','」','）')):cost+=20
                cost += ((limit-w)/limit)**2
                candidate=(cost,[' '.join(tokens[a:b])]+tail[1])
                if best is None or candidate[0]<best[0]:best=candidate
            return best
        result=solve(0,total)
        if result:return result[1]
    return None

def prepare(rows, archives):
    groups=collections.defaultdict(list)
    for row in rows:
        if row.get('category')=='message':groups[row['message_group']].append(row)
    scripts={};changed=[];unresolved=[]
    for group, members in groups.items():
        limit=800 if group in EXCEPTIONS else 720
        name='ysbin\\'+members[0]['script']+'.ybn'
        if name not in scripts:scripts[name]=list(args(split_ybn(archives[name][0])))
        aa=scripts[name];dynamic=False;valid=True
        for index,(a,b) in enumerate(zip(members,members[1:])):
            middle=aa[a['argument']+1:b['argument']]
            if len(middle)==1 and middle[0][3]==NEWLINE:continue
            if index==0 and len(middle)==1 and middle[0][3]==NAME and a['target']=='【' and b['target'].startswith('】'):
                dynamic=True;continue
            valid=False
        body=members[1:] if dynamic else members
        lines=[r['target'] for r in body]
        if dynamic:lines[0]=NAME_TOKEN+lines[0][1:]
        if not any(width(s)>limit for s in lines):continue
        if not valid:
            # Preserve embedded name/numeric fragments in place. Add line breaks
            # only inside an oversized literal; the existing expressions survive.
            explicit=sum(aa[a['argument']+1][3]==NEWLINE for a,b in zip(members,members[1:]) if b['argument']>a['argument']+1)
            assignments=[partition([r['target']],limit) if width(r['target'])>limit else [r['target']] for r in members]
            if all(assignments) and 1+explicit+sum(len(x)-1 for x in assignments)<=3:
                for row,segments in zip(members,assignments):row['_layout_lines']=segments
                changed.append(dict(group=group,limit=limit,before=lines,after=assignments,embedded_expressions_preserved=True))
            else:unresolved.append(dict(group=group,reason='unsupported expression boundary',lines=lines))
            continue
        new=partition(lines,limit)
        if new is None and limit<800:
            limit=800
            new=partition(lines,limit)
        if new is None:
            unresolved.append(dict(group=group,reason='cannot fit whole words within three lines',lines=lines,limit=limit));continue
        assert ''.join(''.join(lines).split())==''.join(''.join(new).split()),group
        assert len(new)<=3 and max(map(width,new))<=limit
        # Keep every existing newline command. Extra newlines are expressions
        # inside the last literal argument, so no command/branch indices move.
        assignments=[[new[i]] for i in range(len(body)-1)]+[new[len(body)-1:]]
        if dynamic:
            assert assignments[0][0].startswith(NAME_TOKEN)
            assignments[0][0]='】'+assignments[0][0][len(NAME_TOKEN):]
        for row,segments in zip(body,assignments):row['_layout_lines']=segments
        changed.append(dict(group=group,limit=limit,before=lines,after=new,widths=list(map(width,new)),dynamic_name=dynamic))
    changed, unresolved = repair_embedded(groups, scripts, changed, unresolved)
    return dict(changed_groups=len(changed),changed=changed,
                unresolved=[u for u in unresolved if u['group']!='yst00496:g0057'],
                preserved_by_user=[u for u in unresolved if u['group']=='yst00496:g0057'],
                limit=720,exception_limit=800,exception_groups=sorted(EXCEPTIONS),runtime_verified=False)

def stream(rows, aa, planned):
    lines=[[]]
    for i,row in enumerate(rows):
        text='\n'.join(row.get('_layout_lines',[row['target']])) if planned else row['target']
        for offset,c in enumerate(text):
            if c=='\n':lines.append([])
            else:lines[-1].append((c,row['id'],offset))
        if i+1<len(rows):
            for _,_,_,b in aa[row['argument']+1:rows[i+1]['argument']]:
                if b==NEWLINE:lines.append([])
                elif b==NAME:lines[-1].extend((c,None,None) for c in '가나다라')
    return lines

def break_records(records, limit):
    text=''.join(c for c,_,_ in records)
    points=[0]+[i for i,(c,row,_) in enumerate(records) if row and c.isspace() and i>0]+[len(records)]
    points=sorted(set(points))
    @functools.lru_cache(None)
    def solve(start):
        if start==len(records):return []
        choices=[]
        for end in points:
            if end<=start:continue
            part=text[start:end].strip()
            if not part:continue
            if width(part)>limit:break
            tail=solve(end)
            if tail is not None:choices.append([end]+tail)
        if not choices:return None
        return min(choices,key=lambda xs:(len(xs),sum((limit-width(text[a:b].strip()))**2 for a,b in zip([start]+xs,xs))))
    return solve(0)

def repair_embedded(groups, scripts, changed, unresolved):
    by={r['group']:r for r in changed}
    for key,rows in groups.items():
        # Explicit user instruction: retain this one unusually long message.
        if key=='yst00496:g0057':continue
        aa=scripts['ysbin\\'+rows[0]['script']+'.ybn']
        limit=by.get(key,{}).get('limit',800 if key in EXCEPTIONS else 720)
        display=stream(rows,aa,True)
        if len(display)<=3 and all(width(''.join(c for c,_,_ in line))<=limit for line in display):continue
        originals=stream(rows,aa,False)
        for bound in [720,800]:
            plans=[break_records(line,bound) for line in originals]
            if not all(plans) or sum(map(len,plans))>3:continue
            cuts=collections.defaultdict(list)
            for line,breaks in zip(originals,plans):
                for point in breaks[:-1]:
                    _,row,offset=line[point]
                    assert row is not None
                    cuts[row].append(offset)
            for row in rows:
                row.pop('_layout_lines',None)
                if row['id'] in cuts:
                    text=row['target'];parts=[];previous=0
                    for point in sorted(cuts[row['id']]):
                        part=text[previous:point]
                        parts.append(part.rstrip() if previous==0 else part.strip());previous=point
                    parts.append(text[previous:].lstrip());row['_layout_lines']=parts
            result=stream(rows,aa,True)
            strings=[''.join(c for c,_,_ in line) for line in result]
            assert len(strings)<=3 and max(map(width,strings))<=bound,key
            by[key]=dict(group=key,limit=bound,before=[''.join(c for c,_,_ in line) for line in originals],after=strings,widths=list(map(width,strings)),embedded_expressions_preserved=True)
            break
        else:
            unresolved.append(dict(group=key,reason='embedded stream cannot fit',lines=[''.join(c for c,_,_ in line) for line in originals]))
    return list(by.values()),[u for u in unresolved if u['group'] not in by]

def expression(segments, encode):
    def literal(text):
        b=encode(text)
        return b'M'+(len(b)+2).to_bytes(2,'little')+b'"'+b+b'"'
    result=literal(segments[0])
    for segment in segments[1:]:result+=NEWLINE+b'\x2b\0\0'+literal(segment)+b'\x2b\0\0'
    return result
