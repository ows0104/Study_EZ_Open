"""One-off lossless question layout, not a service parser or question author."""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import math
import re
import sys
import pymupdf as f

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PREV = HERE.parent / '2026-11-01-infection-jokbo-2026'
OLD = json.loads((PREV / 'upload-plan.json').read_text(encoding='utf-8'))
SOURCE = Path(OLD['source']['path'])
OUT = ROOT / 'output/pdf/감염과 면역_2026_정리본'
FONT = 'C:/Windows/Fonts/malgun.ttf'
BLUE = (.12, .28, .48)
GREY = (.35, .4, .45)
YEAR = re.compile(r'^20\d{2}(?:\s*-\s*\d)?$')
QSTART = re.compile(r'^(R?\d{1,3})\s*\.\s*\S')
ANSWER = re.compile(r'(R?\d{1,3})\s*\.\s*([1-5](?:\s*[,，/]\s*[1-5])*)(?=\s|$)')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def all_lines(doc, pno):
    result=[]
    for block in doc[pno-1].get_text('dict')['blocks']:
        if block['type'] != 0: continue
        for line in block['lines']:
            text=''.join(s['text'] for s in line['spans']).strip()
            if text:
                result.append({'text':text,'bbox':list(line['bbox'])})
    return result

def region_lines(doc, span):
    for pg, rect in clips(doc, *span):
        col=int(rect.x0 >= 298)
        rows=[r for r in all_lines(doc,pg) if (r['bbox'][0] >= 298)==bool(col)
              and r['bbox'][1]>=rect.y0-0.3 and r['bbox'][1]<rect.y1-0.3]
        for row in sorted(rows,key=lambda r:(r['bbox'][1],r['bbox'][0])):
            yield {**row,'page':pg,'col':col}

def clips(doc, start, end):
    # Same continuous column domain as the already verified source edition.
    for pg in range(start[0],end[0]+1):
        for col in (0,1):
            if (pg,col)<tuple(start[:2]) or (pg,col)>tuple(end[:2]): continue
            top=start[2] if (pg,col)==tuple(start[:2]) else 60
            bottom=end[2] if (pg,col)==tuple(end[:2]) else math.floor(doc[pg-1].rect.height-20)
            if bottom-top<=0: continue
            yield pg,f.Rect(0 if col==0 else 298,top,298 if col==0 else doc[pg-1].rect.width,bottom)

def professors(doc):
    tables={}
    for pg,limit in ((2,810),(3,119),(119,610)):
        words=doc[pg-1].get_text('words')
        headers=[w for w in words if re.fullmatch('2[0-6]',w[4]) and w[0]>270 and w[1]<110]
        if pg==3:
            centers={str(y):(295.3+304.3)/2+(26-y)*34.4 for y in range(26,19,-1)}
        else:
            centers={w[4]:(w[0]+w[2])/2 for w in headers}
        assert set(centers)=={str(y) for y in range(20,27)},(pg,centers)
        nums=[w for w in words if 70<w[0]<103 and (w[0]+w[2])/2<103 and w[1]<(limit-5)
              and (w[1]>108 if pg!=3 else True) and re.fullmatch(r'\d+(?:[-,]\d+)?',w[4])]
        nums.sort(key=lambda w:w[1])
        for i,w in enumerate(nums):
            cy=(w[1]+w[3])/2
            low=108 if i==0 and pg!=3 else (0 if i==0 else ((nums[i-1][1]+nums[i-1][3])/2+cy)/2)
            high=limit if i==len(nums)-1 else (cy+(nums[i+1][1]+nums[i+1][3])/2)/2
            cells={y:[] for y in centers}
            for word in words:
                x=(word[0]+word[2])/2; y=(word[1]+word[3])/2
                if x<270 or not low<=y<high:continue
                year=min(centers,key=lambda yy:abs(centers[yy]-x))
                if abs(centers[year]-x)<18 and re.fullmatch(r'[가-힣]{2,4}',word[4]):
                    if word[4] not in cells[year]:cells[year].append(word[4])
            tables[w[4]]=cells
    # The first two numbers in the professor list are reversed relative to the body.
    tables['1'],tables['2']=tables['2'],tables['1']
    for key in ('6','9'):tables[key]=tables['6,9']
    for key in ('10','11'):tables[key]=tables['10-11']
    return tables

def blocks(doc, span):
    rows=list(region_lines(doc,span));events=[]
    for r in rows:
        t=r['text'];box=r['bbox'];kind=None;no=None
        if YEAR.fullmatch(t):kind='year'
        elif (m:=QSTART.match(t)) and box[0]<(88 if r['col']==0 else 331):
            kind='question';no=m.group(1)
        if kind:
            events.append({'kind':kind,'no':no,'label':t,'point':[r['page'],r['col'],max(60,math.floor(box[1])-1)]})
    points=[{'kind':'context','no':None,'label':'原文','point':list(span[0])}]
    points += [e for e in events if tuple(e['point'])>tuple(span[0]) and tuple(e['point'])<tuple(span[1])]
    result=[];year='未記載'
    for i,event in enumerate(points):
        end=points[i+1]['point'] if i+1<len(points) else list(span[1])
        if event['kind']=='year':year=re.sub(r'\s','',event['label'])
        parts=[{'source_page':pg,'clip':list(rect)} for pg,rect in clips(doc,event['point'],end)]
        result.append({**event,'year':year,'end':end,'parts':parts})
    return result

def answer_map(doc, span):
    year=None;out=defaultdict(list);unparsed=[]
    for row in region_lines(doc,span):
        text=row['text']
        if YEAR.fullmatch(text):year=re.sub(r'\s','',text);continue
        if year:
            found=list(ANSWER.finditer(text))
            if found and not re.search(r'이의|번|문항|정답|해설',text):
                for m in found:
                    value=re.sub(r'\s','',m.group(2)).replace('，',',').replace('/',',')
                    out[(year,m.group(1))].append({'answer':value,'page':row['page'],'line':text})
            elif re.match(r'^R?\d+\s*\.',text):unparsed.append({'year':year,**row})
    return out,unparsed

def txt(page,rect,text,size=11,color=GREY):
    page.insert_font(fontname='kr',fontfile=FONT)
    rect=f.Rect(rect)
    if rect.height<size*1.7:rect.y1=rect.y0+size*1.7
    rest=page.insert_textbox(rect,text,fontname='kr',fontsize=size,color=color,lineheight=1.4)
    assert rest>=0,(text,rect,rest)

def base(doc,title,small=''):
    p=doc.new_page(width=595,height=842)
    txt(p,(42,23,553,48),'감염과 면역 | 2026년판 정리본',10,BLUE)
    txt(p,(42,49,553,92),title,15,BLUE)
    if small:txt(p,(42,95,553,121),small,9,GREY)
    p.draw_line((42,118),(553,118),color=(.78,.82,.86),width=.6)
    txt(p,(42,805,520,829),'원문·그림·표 유지 | 정답은 원본 표기 기준',8,GREY)
    txt(p,(523,805,553,829),str(len(doc)),9,GREY)
    return p

def trim(doc,part):
    # Trim only white lateral margins; keep every vertical point in the partition.
    r=f.Rect(part['clip']);pg=doc[part['source_page']-1]
    bounds=[]
    for kind,box in pg.get_bboxlog():
        b=f.Rect(box)
        if b.intersects(r) and kind in ('fill-text','stroke-text','fill-image','fill-path','stroke-path'):
            b=b&r
            if b.width>0 and b.height>0:bounds.append(b)
    if bounds:
        x0=max(r.x0,math.floor(min(b.x0 for b in bounds))-2)
        x1=min(r.x1,math.ceil(max(b.x1 for b in bounds))+2)
        return f.Rect(x0,r.y0,x1,r.y1)
    return r

def visible(doc,part):
    r=f.Rect(part['clip']);pg=doc[part['source_page']-1]
    boxes=[f.Rect(b)&r for kind,b in pg.get_bboxlog() if kind in ('fill-text','stroke-text','fill-image','fill-path','stroke-path') and f.Rect(b).intersects(r)]
    # Ignore tiny line-only tails, but never skip text/images.
    return any(b.width>0 and b.height>0 for b in boxes)

def slice_part(doc,part,maxheight):
    r=trim(doc,part);pg=doc[part['source_page']-1]
    while r.height>maxheight:
        target=r.y0+maxheight
        occupied=[]
        for kind,box in pg.get_bboxlog():
            b=f.Rect(box)
            if b.intersects(r) and kind in ('fill-text','stroke-text','fill-image'):
                occupied.append((max(r.y0,b.y0),min(r.y1,b.y1)))
        candidates=[target-i for i in range(int(maxheight*.7))]
        split=next((y for y in candidates if all(not lo-1<y<hi+1 for lo,hi in occupied)),None)
        if split is None:
            # An unusually tall image is preserved intact at reduced scale.
            yield f.Rect(r);return
        yield f.Rect(r.x0,r.y0,r.x1,split)
        r=f.Rect(r.x0,split,r.x1,r.y1)
    if r.height>.01:yield r

def place(doc,source,parts,title,small,footer,manifest):
    shown=[p for p in parts if visible(source,p)]
    if not shown:return None
    # Aim for 12-14pt original body text. Multiple original-column pieces stay together.
    chunks=[]
    for part in shown:
        for rect in slice_part(source,part,480):
            chunks.append((part,rect))
    total_height=sum(r.height for _,r in chunks)
    together_scale=min(1.5,(550-8*len(chunks))/total_height) if total_height<=550 else 1.5
    first=len(doc)+1;page=None;y=130
    for j,(part,r) in enumerate(chunks):
        scale=min(together_scale,511/r.width,570/r.height)
        h=r.height*scale
        if page is None or y+h>710:
            page=base(doc,title,small+(' | 계속' if page is not None else ''));y=130
        dest=f.Rect(42,y,42+r.width*scale,y+h)
        manifest.append({'output_page':len(doc),'source_page':part['source_page'],'source_clip':list(r),
                         'partition_clip':part['clip'],'dest':list(dest),'scale':scale})
        y+=h+8
    if footer:
        if y+51>788:page=base(doc,title+' | 정답',small);y=130
        page.draw_rect(f.Rect(42,y,553,y+47),fill=(.94,.96,.98),color=None)
        txt(page,(52,y+9,543,y+44),footer,10,BLUE)
    return first

def build(key,meta,source,table):
    units=blocks(source,meta['question_span']);answers,unparsed=answer_map(source,meta['answer_span'])
    counts=Counter((u['year'],u['no']) for u in units if u['kind']=='question')
    runs=[r for r in OLD['lectures'] if r['section']==key]
    current=sorted({p for r in runs for p in r['lecture_payload']['professors'] if re.fullmatch(r'[가-힣]{2,4}',p)})
    history=table.get(key,{})
    for u in units:
        if u['kind']!='question':continue
        candidates=answers.get((u['year'],u['no']),[])
        if len(candidates)==1 and counts[(u['year'],u['no'])]==1:
            u['answer']=candidates[0]['answer'];u['answer_page']=candidates[0]['page']
            u['answer_status']='source_match'
        else:
            u['answer']=None;u['answer_status']='ambiguous' if candidates else 'not_found'
            u['answer_candidates']=candidates
    doc=f.open();p=doc.new_page(width=595,height=842)
    txt(p,(42,48,553,78),'감염과 면역 | 2026년판 족보',19,BLUE)
    txt(p,(42,98,553,180),meta['title'],23,BLUE)
    n=sum(u['kind']=='question' for u in units)
    matched=sum(u.get('answer_status')=='source_match' for u in units)
    txt(p,(42,194,553,227),f'원본 문항 {n}개 | 정답 연결 {matched}개',12,BLUE)
    txt(p,(42,236,553,277),'올해 시간표 담당: '+('·'.join(current) if current else '별도 확인'),11,GREY)
    yy=295
    txt(p,(42,yy,553,320),'교수 이력 (원본 표기)',12,BLUE);yy+=30
    if history:
        for year,names in sorted(history.items(),reverse=True):
            txt(p,(52,yy,553,yy+25),f'20{year}  '+('·'.join(names) or '확인 필요'),10,GREY);yy+=25
    else:
        txt(p,(52,yy,553,yy+45),'CBL·실습·합본은 교수표와 문항 출제자를 임의로 연결하지 않았습니다.',10,GREY);yy+=50
    notes=('연도별 문항과 정답을 함께 배치했습니다.\n'
           '문제·보기·그림·표는 원본 모습을 유지했습니다.\n'
           '원본 정답표의 오류 가능성은 남아 있습니다. 정답 검증·수정본은 아닙니다.\n'
           '정답을 확실히 연결할 수 없는 문항은 확인 표시를 남겼습니다.\n'
           '공용 보기·추가 자료와 원본 정답표는 뒤쪽에서 확인할 수 있습니다.')
    txt(p,(42,max(yy+15,540),553,730),notes,10,GREY)
    txt(p,(42,773,553,820),f'출처: 2026년판 감염과 면역 족보, 원본 {meta["question_span"][0][0]}쪽부터\n강의별 범위가 합본인 경우 해당 합본의 문항을 함께 수록합니다.',8,GREY)
    placements=[];toc=[[1,'단원 및 교수 이력',1]];reference=[];yeargroups=[]
    # Preserve contiguous year blocks, including repeated year labels and shared answers.
    for u in units:
        if u['kind']=='year' or not yeargroups:yeargroups.append([])
        yeargroups[-1].append(u)
    own=[];ref=[];unknown=[]
    for group in yeargroups:
        year=group[0]['year'];authors=history.get(year[2:4],[]) if year.startswith('20') else []
        if current and authors and set(current)==set(authors):own.append(group)
        elif current and authors:ref.append(group)
        else:unknown.append(group)
    # Do not label unknowns as the current professor's questions.
    groups=[('올해 담당 교수와 일치',own),('출제자 구분 없음',unknown),('참고: 다른 담당 교수 연도',ref)]
    for label,batches in groups:
        if not batches:continue
        label_started=False
        for group in batches:
            year=group[0]['year'];year_toc=False
            for u in group:
                if u['kind']!='question':
                    reference.append(u);continue
                footer='정답 '+u['answer']+f'  (원본 정답표 p.{u["answer_page"]})' if u['answer'] else '정답 연결 확인 필요 - 뒤쪽 원본 정답표를 확인하세요.'
                pp=sorted({a['source_page'] for a in u['parts']})
                first=place(doc,source,u['parts'],f'{year} | {u["no"]}번',label+' | 원본 p.'+','.join(map(str,pp)),footer,placements)
                if first:
                    if not label_started:toc.append([1,label,first]);label_started=True
                    if not year_toc:toc.append([2,year,first]);year_toc=True
                    toc.append([3,u['no']+'번',first]);u['output_page']=first
    if reference:
        first=place(doc,source,[a for u in reference for a in u['parts']],
                    '원문 안내·공용 자료','원본 자료 순서 유지','',placements)
        if first:toc.append([1,'원문 안내·공용 자료',first])
    aparts=[{'source_page':pg,'clip':list(r)} for pg,r in clips(source,*meta['answer_span'])]
    first=place(doc,source,aparts,'원본 정답표','단원·연도·번호는 원본 표기를 유지했습니다.','',placements)
    if first:toc.append([1,'원본 정답표',first])
    profpages=[119] if key.isdigit() and int(key)>=49 else [2,3]
    start=len(doc)+1
    for pg in profpages:
        p=doc.new_page(width=595,height=842)
        placements.append({'output_page':len(doc),'source_page':pg,'source_clip':list(source[pg-1].rect),
                           'partition_clip':list(source[pg-1].rect),'dest':list(p.rect),'scale':1.0,'professor_table':True})
    toc.append([1,'원본 교수표·유의사항',start]);doc.set_toc(toc)
    # Subset generated layout BEFORE importing any source text/images. Otherwise
    # adding characters after a cover-only subset silently drops new header glyphs.
    doc.subset_fonts()
    for placement in placements:
        doc[placement['output_page']-1].show_pdf_page(f.Rect(placement['dest']),source,
            placement['source_page']-1,clip=f.Rect(placement['source_clip']),keep_proportion=False)
    path=OUT/f'2026-{key}-족보-정리본.pdf'
    doc.save(path,garbage=3,deflate=True)
    pages=len(doc);doc.close()
    return {'path':str(path),'title':meta['title'],'sha256':digest(path),'page_count':pages,
            'question_count':n,'matched_answers':matched,'units':units,'placements':placements,
            'unparsed_answers':unparsed,'current_professors':current,'professors_by_year':history,
            'question_span':meta['question_span'],'answer_span':meta['answer_span']}

def main():
    assert digest(SOURCE)==OLD['source']['sha256']
    OUT.mkdir(parents=True,exist_ok=True)
    source=f.open(SOURCE);table=professors(source)
    write_json(HERE/'professor-table.json',table)
    files={}
    selected=sys.argv[1:] or list(OLD['files'])
    for key in selected:
        files[key]=build(key,OLD['files'][key],source,table)
        print('PREPARED',key,files[key]['question_count'],'questions',files[key]['page_count'],'pages',flush=True)
    if sys.argv[1:]:
        write_json(HERE/'sample-plan.json',{'source':OLD['source'],'files':files});return
    lectures=[{**r,'path':files[r['section']]['path']} for r in OLD['lectures']]
    plan={**OLD,'files':files,'lectures':lectures,'format':'organized-vector-questions-with-answers'}
    write_json(HERE/'upload-plan.json',plan)
    print('DONE',len(files),'files',len(lectures),'targets',sum(v['question_count'] for v in files.values()),'questions',flush=True)

if __name__=='__main__':main()
