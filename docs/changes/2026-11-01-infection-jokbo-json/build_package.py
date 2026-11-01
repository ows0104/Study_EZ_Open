"""Lossless source-backed JSON and linked media; no question/answer authoring."""
from pathlib import Path
from collections import Counter, OrderedDict
import base64
import hashlib
import html
import json
import math
import re
import shutil
import sys
import pymupdf as f

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'2026-11-01-infection-jokbo-answer-audit'
PLAN=json.loads((BASE/'upload-plan.json').read_text(encoding='utf-8'))
OUT=ROOT/'output/materials/감염과 면역_2026_JSON'
SOURCE=Path(PLAN['source']['path'])
SCALE=3
MARKERS='①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮'
MASTER_PAGES=OrderedDict()

def sha(data):return hashlib.sha256(data).hexdigest()
def file_sha(path):return sha(Path(path).read_bytes())
def save_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def norm(t):return re.sub(r'\s+','',t)
def rel(path):return Path(path).relative_to(OUT).as_posix()

def page_info(doc,pg):
    page=doc[pg-1]
    return {'images':page.get_image_info(xrefs=True),'drawings':page.get_drawings(),
            'bboxlog':page.get_bboxlog()}

def visual_regions(page,info,clip):
    """Visible image instances plus connected vector shapes (including tables)."""
    seeds=[]
    for im in info['images']:
        r=f.Rect(im['bbox'])&clip
        if r.width>0.3 and r.height>0.3:
            seeds.append({'rect':r,'kinds':{'embedded_image'},'xrefs':{im['xref']} if im['xref'] else set()})
    for r in page.cluster_drawings(drawings=info['drawings'],x_tolerance=3,y_tolerance=3):
        r=r&clip
        if r.width>=6 and r.height>=6:
            seeds.append({'rect':r,'kinds':{'vector_or_table'},'xrefs':set()})
    # Merge overlapping visual components so image overlays/borders are not separated.
    merged=[]
    for item in seeds:
        changed=True
        while changed:
            changed=False
            for i,other in enumerate(merged):
                if (item['rect']+(-2,-2,2,2)).intersects(other['rect']):
                    item={'rect':item['rect']|other['rect'],'kinds':item['kinds']|other['kinds'],
                          'xrefs':item['xrefs']|other['xrefs']}
                    merged.pop(i);changed=True;break
        merged.append(item)
    for item in sorted(merged,key=lambda a:(a['rect'].y0,a['rect'].x0)):
        r=item['rect'];r=f.Rect(math.floor(r.x0)-3,math.floor(r.y0)-3,math.ceil(r.x1)+3,math.ceil(r.y1)+3)&clip
        yield {**item,'rect':r}

def labeled_image(pix,label,path):
    # Document layout: a new white label margin around untouched source pixels.
    width=max(540,pix.width+24);height=pix.height+56
    svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="44">'
         '<rect width="100%" height="100%" fill="white"/>'
         f'<text x="12" y="29" font-family="sans-serif" font-size="20" fill="#173655">{html.escape(label)}</text></svg>')
    headerdoc=f.open(stream=svg.encode(),filetype='svg')
    header=headerdoc[0].get_pixmap(matrix=f.Matrix(4/3,4/3),colorspace=f.csRGB,alpha=False)
    data=bytearray(b'\xff'*(width*height*3))
    def paste(src,x,y):
        buf=src.samples
        for row in range(src.height):
            start=((y+row)*width+x)*3
            data[start:start+src.width*3]=buf[row*src.stride:row*src.stride+src.width*3]
    paste(header,0,0);paste(pix,12,44)
    result=f.Pixmap(f.csRGB,width,height,bytes(data),False)
    result.save(path);headerdoc.close()
    return {'body_rect_pixels':[12,44,12+pix.width,44+pix.height],
            'width':width,'height':height,'sha256':file_sha(path)}

def region_record(doc,pg,rect,path):
    # Use one fixed-resolution full-page rendering before cropping. Rendering
    # different clips can change MuPDF's cached JPEG downsampling selection.
    if pg not in MASTER_PAGES:
        MASTER_PAGES[pg]=doc[pg-1].get_pixmap(matrix=f.Matrix(SCALE,SCALE),colorspace=f.csRGB,alpha=False)
        if len(MASTER_PAGES)>8:MASTER_PAGES.popitem(last=False)
    MASTER_PAGES.move_to_end(pg)
    master=MASTER_PAGES[pg]
    bounds=(rect*f.Matrix(SCALE,SCALE)).irect & master.irect
    pix=f.Pixmap(f.csRGB,bounds,False);pix.copy(master,bounds)
    pix.save(path)
    return {'file':rel(path),'source_page':pg,'bbox':list(rect),'render_scale':SCALE,
            'render_method':'full_page_then_crop',
            'width':pix.width,'height':pix.height,'pixel_sha256':sha(pix.samples),
            'sha256':file_sha(path)},pix

def content_lines(page,rect):
    rows=[]
    for block in page.get_text('dict',clip=rect)['blocks']:
        if block['type']!=0:continue
        for ln in block['lines']:
            t=''.join(sp['text'] for sp in ln['spans'])
            if t.strip():rows.append({'text':t,'bbox':list(ln['bbox'])})
    return rows

def parse_body(raw,no):
    body=re.sub(r'^\s*'+re.escape(no)+r'\s*\.\s*','',raw,count=1)
    hits=list(re.finditer('['+MARKERS+']',body))
    labels=[m.group() for m in hits]
    if labels==list('①②③④⑤'):
        stem=body[:hits[0].start()].strip()
        choices=[{'label':m.group(),'text':body[m.end():hits[i+1].start() if i+1<len(hits) else len(body)].strip()} for i,m in enumerate(hits)]
        return stem,choices,'five_circled_choices'
    return body.strip(),[],'preserved_in_body'

def extract_unit(doc,cache,key,unit,ordinal,kind='question'):
    year=unit['year'];no=unit.get('no')
    uid=f'S{key}-{year}-Q{no}-O{ordinal}' if kind=='question' else f'S{key}-N{ordinal:03d}'
    result={'id':uid,'kind':kind,'source_unit_kind':unit.get('kind',kind),'year':year,'number':no,'source_order':ordinal,
            'source_regions':[],'content_blocks':[],'images':[]}
    texts=[]
    figure_index=0
    for ri,part in enumerate(unit['parts'],1):
        pg=part['source_page'];r=f.Rect(part['clip']);page=doc[pg-1]
        raw=page.get_text(clip=r)
        texts.append(raw)
        preview_path=OUT/'source-excerpts'/f'{uid}-R{ri:02d}.png'
        preview,pix=region_record(doc,pg,r,preview_path)
        preview['text_original']=raw;result['source_regions'].append(preview)
        events=[]
        for row in content_lines(page,r):
            events.append((row['bbox'][1],0,{'type':'text','text':row['text'],'source_page':pg,'bbox':row['bbox']}))
        for visual in visual_regions(page,cache[pg],r):
            figure_index+=1;image_id=f'{uid}-F{figure_index:02d}'
            figure_path=OUT/'images'/f'{image_id}.png'
            record,imagepix=region_record(doc,pg,visual['rect'],figure_path)
            record.update({'id':image_id,'question_id':uid if kind=='question' else None,'material_id':uid,
                           'order':figure_index,'kinds':sorted(visual['kinds']),
                           'source_image_xrefs':sorted(visual['xrefs']),
                           'source_excerpt_file':preview['file']})
            gpt_path=OUT/'gpt-images'/f'{image_id}.png'
            record['gpt_image']={'file':rel(gpt_path),**labeled_image(imagepix,image_id+f' | source p.{pg}',gpt_path)}
            result['images'].append(record)
            events.append((visual['rect'].y0,1,{'type':'image','image_id':image_id,'source_page':pg,'bbox':list(visual['rect'])}))
        result['content_blocks'].extend(e[2] for e in sorted(events,key=lambda a:(a[0],a[1])))
    raw=''.join(texts)
    result['text_original']=raw;result['text_sha256']=sha(raw.encode())
    if kind=='question':
        stem,choices,status=parse_body(raw,no)
        result.update({'stem':stem,'choices':choices,'choice_parse_status':status,
                       'answer':{'value':unit.get('answer'),'status':unit['answer_status'],
                                 'source_page':unit.get('answer_page'),
                                 'candidates':unit.get('answer_candidates',[])},
                       'duplicate_identical_source':unit.get('duplicate_identical_source',False),
                       'organized_pdf_page':unit.get('output_page')})
    return result

def archive_images(doc):
    xrefs={}
    for page in doc:
        for im in page.get_images(full=True):
            if im[0] not in xrefs:xrefs[im[0]]={'xref':im[0],'soft_mask_xref':im[1], 'pages':[]}
            if page.number+1 not in xrefs[im[0]]['pages']:xrefs[im[0]]['pages'].append(page.number+1)
    records=[]
    for xref,row in sorted(xrefs.items()):
        data=doc.extract_image(xref)
        path=OUT/'source-images'/f'xref-{xref:05d}.{data["ext"]}'
        path.write_bytes(data['image'])
        raw_path=OUT/'source-images'/f'xref-{xref:05d}.stream'
        raw=doc.xref_stream_raw(xref);raw_path.write_bytes(raw)
        record={**row,'file':rel(path),'sha256':file_sha(path),'raw_stream_file':rel(raw_path),'raw_stream_sha256':sha(raw),
                'width':data['width'],'height':data['height']}
        if row['soft_mask_xref']:
            mask=doc.extract_image(row['soft_mask_xref']);mp=OUT/'source-images'/f'mask-{row["soft_mask_xref"]:05d}.{mask["ext"]}'
            mp.write_bytes(mask['image']);record['mask_file']=rel(mp);record['mask_sha256']=file_sha(mp)
        records.append(record)
    return records

def export_md(section):
    # This is a mechanical serialization of canonical JSON, not independently edited prose.
    lines=[f'# {section["title"]}', '',f'단원 ID: {section["id"]}',
           '아래 그림 ID에 대응하는 gpt-images PNG를 실제 이미지로 함께 첨부하세요.',
           '그림 링크만으로 GPT에 이미지가 전달되는 것은 아닙니다.',
           '정답은 원본 표기이며 연결 확인 상태를 유지합니다.', '']
    attachments=[]
    for q in section['questions']:
        answer=q['answer']['value'] or '연결 확인 필요'
        lines += [f'## {q["year"]}년 {q["number"]}번',f'문항 ID: {q["id"]}',
                  f'정답: {answer}',f'정답 상태: {q["answer"]["status"]}', '', q['text_original'].strip(), '']
        for im in q['images']:
            image=im['gpt_image']['file'];attachments.append(image)
            lines += [f'그림 ID: {im["id"]} (원본 p.{im["source_page"]})',
                      f'![{im["id"]}](../{image})','']
        if q['images']:
            lines += ['원문 배치 대조: '+', '.join(r['file'] for r in q['source_regions']), '']
        if q.get('layout_images'):
            lines += ['그림 보기형 문항: 보기 번호와 사진의 원본 배치를 아래 대조 이미지에서 함께 확인하세요.','']
            for im in q['layout_images']:
                image=im['gpt_image']['file'];attachments.append(image)
                lines += [f'원문 배치 ID: {im["id"]}',f'![{im["id"]}](../{image})','']
    if section['source_notes']:
        lines += ['## 원본 안내 및 보충 자료','']
        for material in section['source_notes']:
            lines += [f'### {material["id"]}',material['text_original'].strip(),'']
            # Source chapter-title frames stay in the archive, rather than consuming
            # an extra image attachment when the same title is already in the MD.
            if material.get('source_unit_kind')=='context':continue
            for im in material['images']:
                image=im['gpt_image']['file'];attachments.append(image)
                lines += [f'그림 ID: {im["id"]}',f'![{im["id"]}](../{image})','']
    if section['answer_table_original']:
        lines += ['## 원본 정답표 (대조용)','',section['answer_table_original']['text_original'],'']
    md_path=OUT/'gpt'/f'{section["id"]}.md'
    md_path.write_text('\n'.join(lines),encoding='utf-8')
    listing=OUT/'gpt'/f'{section["id"]}-첨부목록.txt'
    listing.write_text('MD 파일과 아래 PNG 파일을 같은 대화에 첨부하세요. 그림이 많으면 문항별로 나누세요.\n'
                       + '\n'.join(dict.fromkeys(attachments))+'\n',encoding='utf-8')
    return {'markdown':rel(md_path),'image_files':list(dict.fromkeys(attachments)),'attachment_list':rel(listing)}

def make_section(doc,cache,key,meta):
    section={'schema_version':'1.0','id':f'S{key}','subject':'감염과 면역','edition':2026,
             'title':meta['title'],'paths_relative_to':'package_root',
             'source_pdf':'source/감염과 면역 족보_2026_원본.pdf',
             'current_professors':meta['current_professors'],'professors_by_year':meta['professors_by_year'],
             'lectures':[r['lecture_payload'] for r in PLAN['lectures'] if r['section']==key],
             'questions':[],'source_notes':[]}
    qi=0;ni=0
    for unit in meta['units']:
        if unit['kind']=='question':
            qi+=1;q=extract_unit(doc,cache,key,unit,qi)
            # Stable question IDs remain unique even when the source repeats a number.
            authors=meta['professors_by_year'].get(unit['year'][2:4],[]) if unit['year'].startswith('20') else []
            q['professors_from_source_table']=authors
            q['professor_relation']=('same_as_current' if authors and set(authors)==set(meta['current_professors'])
                                     else 'other_or_mixed' if authors and meta['current_professors'] else 'unknown')
            section['questions'].append(q)
        else:
            ni+=1;section['source_notes'].append(extract_unit(doc,cache,key,unit,ni,'source_note'))
    answer_parts=[]
    # Reuse the fixed source-column domain. No new heading inference.
    for pg in range(meta['answer_span'][0][0],meta['answer_span'][1][0]+1):
        start,end=meta['answer_span']
        for col in (0,1):
            if (pg,col)<tuple(start[:2]) or (pg,col)>tuple(end[:2]):continue
            top=start[2] if (pg,col)==tuple(start[:2]) else 60
            bottom=end[2] if (pg,col)==tuple(end[:2]) else math.floor(doc[pg-1].rect.height-20)
            if bottom>top:answer_parts.append({'source_page':pg,'clip':[0 if col==0 else 298,top,298 if col==0 else doc[pg-1].rect.width,bottom]})
    a=extract_unit(doc,cache,key,{'year':'原本','no':None,'parts':answer_parts},999,'answer_table')
    section['answer_table_original']=a
    section_path=OUT/'sections'/f'S{key}.json';save_json(section_path,section)
    # Read the persisted canonical representation before making human/GPT exports.
    persisted=json.loads(section_path.read_text(encoding='utf-8'))
    return section,{'id':section['id'],'title':meta['title'],'json_file':rel(section_path),
                    'question_count':len(section['questions']),**export_md(persisted)}

def main():
    assert file_sha(SOURCE)==PLAN['source']['sha256']
    assert not OUT.exists(),'Keep an existing package immutable; create a new version instead.'
    for d in ('sections','images','gpt-images','source-excerpts','source','source-images','gpt'):
        (OUT/d).mkdir(parents=True,exist_ok=True)
    shutil.copyfile(SOURCE,OUT/'source/감염과 면역 족보_2026_원본.pdf')
    doc=f.open(SOURCE);cache={pg+1:page_info(doc,pg+1) for pg in range(len(doc))}
    source_images=archive_images(doc)
    catalog={'schema_version':'1.0','subject':'감염과 면역','edition':2026,'paths_relative_to':'package_root',
             'source':{'file':'source/감염과 면역 족보_2026_원본.pdf','sha256':PLAN['source']['sha256'],'pages':len(doc)},
             'provenance':{'baseline_plan_sha256':file_sha(BASE/'upload-plan.json'),
                           'medical_content_edited':False,'answers_medically_verified':False},
             'sections':[],'source_images':source_images,'lectures':[],'answer_links_to_review':[]}
    all_questions=[];stats=Counter()
    for key,meta in PLAN['files'].items():
        sec,entry=make_section(doc,cache,key,meta);catalog['sections'].append(entry)
        all_questions.extend({**q,'section_id':sec['id'],'section_title':sec['title']} for q in sec['questions'])
        for q in sec['questions']:
            stats['questions']+=1;stats['question_figures']+=len(q['images'])
            stats['matched_answers']+=q['answer']['status']=='source_match'
            if q['answer']['status']!='source_match':
                catalog['answer_links_to_review'].append({'question_id':q['id'],'section':key,'title':sec['title'],
                    'year':q['year'],'number':q['number'],'status':q['answer']['status'],
                    'source_pages':sorted({r['source_page'] for r in q['source_regions']})})
        stats['all_visual_regions']+=sum(len(m['images']) for m in sec['questions']+sec['source_notes']+[sec['answer_table_original']])
        stats['source_excerpt_regions']+=sum(len(m['source_regions']) for m in sec['questions']+sec['source_notes']+[sec['answer_table_original']])
        print('PREPARED',key,len(sec['questions']),'questions',sum(len(q['images']) for q in sec['questions']),'figures',flush=True)
    for row in PLAN['lectures']:
        catalog['lectures'].append({'run_id':row['run_id'],'section_id':'S'+row['section'],
                                    'json_file':f'sections/S{row["section"]}.json','gpt_markdown':f'gpt/S{row["section"]}.md',
                                    'lecture':row['lecture_payload']})
    catalog['counts']={**dict(stats),'sections':69,'lectures':80,'source_image_resources':len(source_images),
                       'answer_links_to_review':len(catalog['answer_links_to_review'])}
    save_json(OUT/'catalog.json',catalog)
    save_json(OUT/'questions.json',{'schema_version':'1.0','paths_relative_to':'package_root','questions':all_questions})
    save_json(OUT/'answer-links-to-review.json',catalog['answer_links_to_review'])
    readme=('감염과 면역 2026년판 족보 - JSON과 연결 그림 자료\n\n'
            'catalog.json: 단원·강의 연결과 전체 목록\n'
            'questions.json: 전체 문항; sections/: 단원별 JSON\n'
            'images/: 원본에 보이는 사진·표·도식 PNG\n'
            'gpt-images/: 같은 그림에 문항/그림 ID를 바깥 여백으로 표시한 GPT 첨부용 PNG\n'
            'source-excerpts/: 빠짐없이 보관한 원문 지면 대조용 PNG\n'
            'source/: 원본 PDF; source-images/: 원본 압축 이미지와 추출본·투명도 마스크\n'
            'gpt/: JSON에서 생성한 강의별 MD와 그림 첨부 목록\n\n'
            'ChatGPT 웹에 전달하기\n'
            '1. ZIP을 풀고 catalog.json에서 수업/단원을 찾습니다.\n'
            '2. gpt 폴더의 해당 MD와 첨부목록에 적힌 gpt-images PNG를 같은 메시지에 첨부합니다.\n'
            '3. 그림이 많으면 문항 단위로 나눕니다. 그림 ID와 문항 ID는 실제 그림 여백에도 표시됩니다.\n'
            '4. 먼저 그림별 대응 문항과 읽히지 않는 부분을 확인한 뒤 분석을 요청합니다.\n'
            'MD의 링크·JSON의 파일 경로만으로 그림이 AI에 전달되는 것은 아닙니다.\n\n'
            '원문 보존\n'
            '문항 원문은 text_original, 배치와 그림은 content_blocks/source_regions/images에 있습니다.\n'
            '확실한 ①~⑤ 보기만 별도 choices로 분리했고 그 외 보기 형식은 본문에 그대로 보존합니다.\n'
            '정답은 원본 표기 연결이며 의학적으로 검증·정정한 답안이 아닙니다.\n'
            '기존 19개 연도·번호·단원 불일치는 answer-links-to-review.json에 유지했습니다.\n'
            '원본의 동일 번호·동일 문항 중복도 고유 ID로 각각 보존했습니다.\n')
    (OUT/'사용안내.txt').write_text(readme,encoding='utf-8')
    # Public, portable contract: every relative path resolves under this package.
    save_json(OUT/'schema.json',{'schema_version':'1.0','canonical':'sections/*.json',
        'question_fields':{'id':'unique stable source occurrence ID','text_original':'unaltered source text',
          'stem':'source text before reliably parsed choices, otherwise entire source body',
          'choices':'only split when exactly one ordered ①②③④⑤ set is present',
          'content_blocks':'ordered source text and image references with PDF coordinates',
          'images':'rendered visual regions with hashes, coordinates and labeled GPT copies',
          'source_regions':'complete source region previews and exact original text',
          'answer':'source value/status/page, not independent medical verification'}})
    files=[{'file':rel(path),'bytes':path.stat().st_size,'sha256':file_sha(path)} for path in sorted(OUT.rglob('*')) if path.is_file()]
    save_json(OUT/'manifest.json',{'schema_version':'1.0','files':files})
    save_json(HERE/'artifact.json',{'output_folder':str(OUT),'catalog':str(OUT/'catalog.json'),
        'baseline_plan_sha256':file_sha(BASE/'upload-plan.json'),'counts':catalog['counts']})
    print(json.dumps(catalog['counts'],ensure_ascii=False),flush=True)

if __name__=='__main__':main()
