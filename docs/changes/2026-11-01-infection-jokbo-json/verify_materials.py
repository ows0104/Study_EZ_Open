"""Check actual source text, source pixels, visual coverage, and data references."""
from pathlib import Path
from collections import Counter,OrderedDict
import hashlib,json,re,sys
import pymupdf as f

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import build_package as b

def safe(path):
    p=(b.OUT/path).resolve()
    assert p.is_relative_to(b.OUT.resolve()) and p.is_file(),('unsafe/missing',path)
    return p
def read(path):return json.loads(safe(path).read_text(encoding='utf-8'))
def norm(t):return re.sub(r'\s+','',t)
MASTERS=OrderedDict()
PIXEL_BASELINE={}
BASELINE_COUNT=0
if (HERE/'pixel-baseline-records.json').exists():
    proof=json.loads((HERE/'pixel-baseline-verification.json').read_text(encoding='utf-8'))
    baseline=json.loads((HERE/'pixel-baseline-records.json').read_text(encoding='utf-8'))
    assert proof['status']=='passed' and proof['manifest_sha256']==baseline['manifest_sha256']==b.file_sha(HERE/'pixel-baseline-manifest.json')
    assert baseline['source_sha256']==b.PLAN['source']['sha256']
    PIXEL_BASELINE=baseline['records']
def check_png(doc,record):
    global BASELINE_COUNT
    path=safe(record['file']);r=f.Rect(record['bbox']);pg=doc[record['source_page']-1]
    assert b.file_sha(path)==record['sha256']
    keys=('file','source_page','bbox','render_scale','render_method','width','height','pixel_sha256','sha256')
    if PIXEL_BASELINE.get(record['file'])=={k:record[k] for k in keys}:
        got=f.Pixmap(path);assert b.sha(got.samples)==record['pixel_sha256']
        assert (got.width,got.height)==(record['width'],record['height'])
        BASELINE_COUNT+=1
        return got
    pno=record['source_page']
    if pno not in MASTERS:
        MASTERS[pno]=pg.get_pixmap(matrix=f.Matrix(3,3),colorspace=f.csRGB,alpha=False)
        if len(MASTERS)>8:MASTERS.popitem(last=False)
    MASTERS.move_to_end(pno)
    master=MASTERS[pno];box=(r*f.Matrix(3,3)).irect & master.irect
    assert record['render_method']=='full_page_then_crop' and record['render_scale']==3
    got=f.Pixmap(path)
    assert (box.width,box.height)==(record['width'],record['height'])==(got.width,got.height)
    samples=master.samples
    expected=b''.join(samples[y*master.stride+box.x0*3:y*master.stride+box.x1*3] for y in range(box.y0,box.y1))
    assert expected==got.samples,(record['file'],'source pixels')
    assert b.sha(got.samples)==record['pixel_sha256']
    return got

def main():
    catalog=read('catalog.json');manifest=read('manifest.json')
    baseline=b.PLAN
    assert b.file_sha(safe(catalog['source']['file']))==baseline['source']['sha256']==b.file_sha(b.SOURCE)
    assert catalog['provenance']['baseline_plan_sha256']==b.file_sha(b.BASE/'upload-plan.json')
    doc=f.open(safe(catalog['source']['file']))
    assert len(doc)==183 and len(catalog['sections'])==69 and len(catalog['lectures'])==80
    assert [(r['run_id'],r['section_id']) for r in catalog['lectures']]==[(r['run_id'],'S'+r['section']) for r in baseline['lectures']]
    expected_files={r['file'] for r in manifest['files']}
    actual_files={p.relative_to(b.OUT).as_posix() for p in b.OUT.rglob('*') if p.is_file() and p.name!='manifest.json'}
    assert expected_files==actual_files
    for row in manifest['files']:
        p=safe(row['file']);assert p.stat().st_size==row['bytes'] and b.file_sha(p)==row['sha256']
    ids=[];image_ids=[];all_q=[];unmatched=[];regions=figures=covered=0;matched=0;choice_count=0
    source_image_cache={}
    def images_on(pg):
        if pg not in source_image_cache:source_image_cache[pg]=doc[pg-1].get_image_info(xrefs=True)
        return source_image_cache[pg]
    for entry in catalog['sections']:
        s=read(entry['json_file']);key=s['id'][1:];meta=baseline['files'][key]
        assert s['title']==meta['title'] and s['current_professors']==meta['current_professors']
        assert s['professors_by_year']==meta['professors_by_year']
        original_q=[u for u in meta['units'] if u['kind']=='question']
        assert len(s['questions'])==len(original_q)==entry['question_count']
        md=safe(entry['markdown']).read_text(encoding='utf-8')
        declared_attachments=set(entry['image_files'])
        assert all(safe(p) for p in declared_attachments)
        for q,u in zip(s['questions'],original_q):
            assert (q['year'],q['number'])==(u['year'],u['no'])
            assert q['answer']['value']==u.get('answer') and q['answer']['status']==u['answer_status']
            assert q['answer']['source_page']==u.get('answer_page')
            assert q['duplicate_identical_source']==u.get('duplicate_identical_source',False)
            expected=''.join(doc[x['source_page']-1].get_text(clip=f.Rect(x['clip'])) for x in u['parts'])
            assert q['text_original']==expected and b.sha(expected.encode())==q['text_sha256']
            assert q['text_original'].strip() in md and q['id'] in md
            if q['choice_parse_status']=='five_circled_choices':
                assert [c['label'] for c in q['choices']]==list('①②③④⑤')
                body=re.sub(r'^\s*'+re.escape(q['number'])+r'\s*\.\s*','',expected,count=1)
                assert norm(q['stem']+''.join(c['label']+c['text'] for c in q['choices']))==norm(body)
                choice_count+=1
            else:assert q['choices']==[]
            if q['answer']['status']=='source_match':matched+=1
            else:unmatched.append((key,q['year'],q['number']))
            ids.append(q['id']);all_q.append({**q,'section_id':s['id'],'section_title':s['title']})
            if q.get('layout_images'):
                assert q['visual_layout_required'] and any(not c['text'].strip() for c in q['choices'])
                assert len(q['layout_images'])==len(q['source_regions'])
                for layout,region in zip(q['layout_images'],q['source_regions']):
                    assert all(layout[k]==region[k] for k in ('file','source_page','bbox','pixel_sha256'))
                    base=check_png(doc,layout);labeled=layout['gpt_image'];actual=f.Pixmap(safe(labeled['file']))
                    assert b.file_sha(safe(labeled['file']))==labeled['sha256']
                    x0,y0,x1,y1=labeled['body_rect_pixels'];a=actual.samples;v=base.samples
                    assert x1-x0==base.width and y1-y0==base.height
                    assert all(a[(y0+y)*actual.stride+x0*3:(y0+y)*actual.stride+x1*3]==v[y*base.stride:y*base.stride+base.width*3] for y in range(base.height))
                    assert labeled['file'] in declared_attachments and layout['id'] in md
        materials=s['questions']+s['source_notes']+[s['answer_table_original']]
        for m in materials:
            expected_raw=''
            wanted_text=[]
            for region in m['source_regions']:
                check_png(doc,region);regions+=1
                pg=doc[region['source_page']-1];r=f.Rect(region['bbox'])
                raw=pg.get_text(clip=r);assert raw==region['text_original'];expected_raw+=raw
                for block in pg.get_text('dict',clip=r)['blocks']:
                    if block['type']==0:
                        for line in block['lines']:
                            t=''.join(sp['text'] for sp in line['spans'])
                            if t.strip():wanted_text.append((region['source_page'],t))
                # All actually visible embedded images must be linked to a PNG
                # belonging to the same source region and question/material.
                for info in images_on(region['source_page']):
                    box=f.Rect(info['bbox'])&r
                    if box.width<=.3 or box.height<=.3:continue
                    assert any(im['source_page']==region['source_page'] and f.Rect(im['bbox']).contains(box)
                               for im in m['images']),(m['id'],'unlinked image',box)
                    covered+=1
            assert expected_raw==m['text_original'] and b.sha(expected_raw.encode())==m['text_sha256']
            assert Counter(wanted_text)==Counter((c['source_page'],c['text']) for c in m['content_blocks'] if c['type']=='text')
            assert {c['image_id'] for c in m['content_blocks'] if c['type']=='image'}=={im['id'] for im in m['images']}
            for im in m['images']:
                pix=check_png(doc,im);figures+=1;image_ids.append(im['id'])
                assert im['material_id']==m['id']
                assert any(r['source_page']==im['source_page'] and f.Rect(r['bbox']).contains(f.Rect(im['bbox'])) for r in m['source_regions'])
                labeled=im['gpt_image'];lp=safe(labeled['file']);assert b.file_sha(lp)==labeled['sha256']
                actual=f.Pixmap(lp);x0,y0,x1,y1=labeled['body_rect_pixels']
                assert x1-x0==pix.width and y1-y0==pix.height
                assert (actual.width,actual.height)==(labeled['width'],labeled['height'])
                a=actual.samples;v=pix.samples
                assert all(a[(y0+y)*actual.stride+x0*3:(y0+y)*actual.stride+x1*3]==v[y*pix.stride:y*pix.stride+pix.width*3] for y in range(pix.height)),(im['id'],'label altered source pixels')
                if m['kind']=='question':assert labeled['file'] in declared_attachments and im['id'] in md
        print('VERIFIED',s['id'],len(s['questions']),'questions',flush=True)
    assert len(ids)==len(set(ids))==850 and len(image_ids)==len(set(image_ids))==catalog['counts']['all_visual_regions']
    assert matched==831 and len(unmatched)==19
    expected_unmatched=[(key,u['year'],u['no']) for key,m in baseline['files'].items() for u in m['units'] if u.get('answer_status') in ('not_found','ambiguous')]
    assert unmatched==expected_unmatched
    assert read('questions.json')['questions']==all_q
    for record in catalog['source_images']:
        assert b.file_sha(safe(record['file']))==record['sha256']
        assert doc.xref_stream_raw(record['xref'])==safe(record['raw_stream_file']).read_bytes()
        if record.get('mask_file'):assert b.file_sha(safe(record['mask_file']))==record['mask_sha256']
    result={'status':'passed','questions':850,'sections':69,'lectures':80,'matched_answers':831,
            'answer_links_to_review':19,'verified_source_png_regions':regions,'verified_visual_pngs':figures,
            'visible_embedded_image_instances_linked':covered,'original_image_resources':len(catalog['source_images']),
            'choice_sets_split_without_text_loss':choice_count,'manifest_sha256':b.file_sha(b.OUT/'manifest.json'),
            'catalog_sha256':b.file_sha(b.OUT/'catalog.json')}
    result['previously_verified_source_pixel_regions_reused']=BASELINE_COUNT
    result['image_only_choice_layouts_verified']=sum(len(q.get('layout_images',[])) for q in all_q)
    b.save_json(HERE/'materials-verification.json',result)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
