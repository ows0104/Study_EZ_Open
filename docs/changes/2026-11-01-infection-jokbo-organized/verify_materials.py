"""Read-only completeness and independent inverse-render verification."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import sys
import pymupdf as f

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import organize as o

def norm(text):return re.sub(r'\s+','',text)

def main():
    plan_path=HERE/'upload-plan.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    old=json.loads((o.PREV/'upload-plan.json').read_text(encoding='utf-8'))
    assert o.digest(plan['source']['path'])==plan['source']['sha256']==old['source']['sha256']
    source=f.open(plan['source']['path'])
    assert len(plan['files'])==69 and len(plan['lectures'])==80
    assert [(r['run_id'],r['section']) for r in plan['lectures']]==[(r['run_id'],r['section']) for r in old['lectures']]
    fragments=0;questions=0;matched=0;images=set();max_diff=0;max_inverse_diff=0;checks=[]
    for key,meta in plan['files'].items():
        assert o.digest(meta['path'])==meta['sha256']
        doc=f.open(meta['path'])
        assert len(doc)==meta['page_count']
        assert not any(list(p.annots() or []) for p in doc)
        units=meta['units'];span=meta['question_span']
        assert units[0]['point']==span[0] and units[-1]['end']==span[1]
        assert all(a['end']==b['point'] for a,b in zip(units,units[1:]))
        assert all(tuple(u['point'])<tuple(u['end']) for u in units)
        # Every source text/image-bearing partition has a displayed placement.
        expected=[]
        for u in units:expected.extend(u['parts'])
        expected.extend({'source_page':pg,'clip':list(r)} for pg,r in o.clips(source,*meta['answer_span']))
        for part in expected:
            pg=source[part['source_page']-1];r=f.Rect(part['clip'])
            placements=[x for x in meta['placements'] if x['source_page']==part['source_page'] and x['partition_clip']==part['clip']]
            if o.visible(source,part):
                assert placements,(key,'missing region',part)
                boxes=sorted([f.Rect(x['source_clip']) for x in placements],key=lambda b:b.y0)
                assert abs(boxes[0].y0-r.y0)<.01 and abs(boxes[-1].y1-r.y1)<.01,(key,'partition ends',part)
                assert all(abs(a.y1-b.y0)<.01 for a,b in zip(boxes,boxes[1:])),(key,'partition gap',part)
                # A lateral trim can remove whitespace only (render all removed margins).
                for margin in [f.Rect(r.x0,r.y0,boxes[0].x0,r.y1),f.Rect(boxes[0].x1,r.y0,r.x1,r.y1)]:
                    if margin.width>.01:
                        pix=pg.get_pixmap(clip=margin,colorspace=f.csGRAY)
                        assert min(pix.samples,default=255)>245,(key,'nonwhite trimmed margin',part)
            else:
                pix=pg.get_pixmap(clip=r,colorspace=f.csGRAY)
                assert min(pix.samples,default=255)>245,(key,'skipped ink',part)
        for placement in meta['placements']:
            pg=source[placement['source_page']-1];r=f.Rect(placement['source_clip'])
            actual=doc[placement['output_page']-1];dest=f.Rect(placement['dest'])
            assert actual.rect.contains(dest)
            if not placement.get('professor_table'):
                assert dest.y0>=129 and dest.y1<=711 and dest.x0>=41 and dest.x1<=554
            # Undo the authored scale/translation and independently render the actual
            # saved output; this catches lost transparency/images and clipping.
            proof=f.open();p=proof.new_page(width=r.width,height=r.height)
            p.show_pdf_page(p.rect,doc,placement['output_page']-1,clip=dest,keep_proportion=False)
            want=pg.get_pixmap(clip=r,colorspace=f.csGRAY)
            got=p.get_pixmap(colorspace=f.csGRAY)
            assert (want.width,want.height)==(got.width,got.height),(key,'dimensions',placement)
            a=want.samples;b=got.samples
            diff=sum(abs(x-y) for x,y in zip(a,b))/len(a)
            max_inverse_diff=max(max_inverse_diff,diff)
            # Image resampling/antialiasing on a scale round-trip can differ.
            # Compare the saved output against an independent source rendering at
            # the SAME output coordinates as the decisive pixel check.
            expected=f.open();ep=expected.new_page(width=595,height=842)
            ep.show_pdf_page(dest,source,placement['source_page']-1,clip=r,keep_proportion=False)
            a=ep.get_pixmap(clip=dest,colorspace=f.csGRAY).samples
            b=actual.get_pixmap(clip=dest,colorspace=f.csGRAY).samples
            assert len(a)==len(b)
            direct_diff=sum(abs(x-y) for x,y in zip(a,b))/len(a)
            max_diff=max(max_diff,direct_diff)
            assert direct_diff<.1,(key,'saved rendering differs from direct source',direct_diff,placement)
            expected.close()
            assert norm(pg.get_text(clip=r))==norm(p.get_text()),(key,'text difference',placement)
            # The original compressed image data must survive the import unchanged.
            source_images={hashlib.sha256(source.xref_stream(im[0])).hexdigest() for im in pg.get_images()}
            output_images={hashlib.sha256(proof.xref_stream(im[0])).hexdigest() for im in p.get_images()}
            assert source_images<=output_images,(key,'image bytes')
            images.update((placement['source_page'],h) for h in source_images)
            proof.close();fragments+=1
        amap,_=o.answer_map(source,meta['answer_span'])
        qcount=Counter((u['year'],u['no']) for u in units if u['kind']=='question')
        for u in units:
            if u['kind']!='question':continue
            questions+=1
            assert 'output_page' in u,(key,'question omitted',u)
            output_text=doc[u['output_page']-1].get_text()
            assert norm(u['year']+' | '+u['no']+'번') in norm(output_text)
            candidates=amap.get((u['year'],u['no']),[])
            if u['answer_status']=='source_match':
                assert len(candidates)==qcount[(u['year'],u['no'])]==1
                assert u['answer']==candidates[0]['answer']
                matched+=1
            else:assert u['answer'] is None
        checks.append({'section':key,'pages':len(doc),'questions':meta['question_count'],'sha256':meta['sha256']})
        doc.close();print('VERIFIED',key,'regions',len(meta['placements']),flush=True)
    result={'status':'passed','derived_pdfs':69,'lecture_targets':80,'questions':questions,'source_matched_answers':matched,
            'inverse_render_regions':fragments,'preserved_source_image_streams':len(images),'max_mean_pixel_difference':max_diff,
            'max_inverse_resampling_difference':max_inverse_diff,
            'plan_sha256':o.digest(plan_path),'files':checks}
    o.write_json(HERE/'materials-verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False))

if __name__=='__main__':main()
