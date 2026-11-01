"""Independently verify all saved source regions, metadata, answers and priorities."""
from collections import Counter
import json, re
import pymupdf as f
import build_materials as b

def norm(text): return re.sub(r'\s+', '', text)

def main():
    plan=b.read(b.HERE/'upload-plan.json')
    for path,digest in plan['inputs'].items(): assert b.sha(path)==digest
    assert b.sha(plan['source_path'])==plan['source']['sha256']
    source=f.open(plan['source_path']); regions=0; max_diff=0; counts=Counter(); summaries=[]; unique={}
    assert len(plan['lectures'])==80 and len({r['run_id'] for r in plan['lectures']})==80
    for key,meta in plan['files'].items():
        section=b.read(b.PACKAGE/'sections'/f'{meta["section_id"]}.json')
        doc=f.open(meta['path']); assert len(doc)==meta['pages'] and b.sha(meta['path'])==meta['sha256']
        assert not any('교수표' in row[1] or '교수 이력' in row[1] for row in doc.get_toc())
        original={q['id']:q for q in section['questions']}
        for qid,q in original.items():
            assert qid not in unique or unique[qid]==q['answer']
            unique[qid]=q['answer']
        assert Counter(q['id'] for q in meta['questions'])==Counter(original.keys())
        seen_reference=False; last_year_by_priority={}
        for q in meta['questions']:
            src=original[q['id']];names=src['professors_from_source_table']
            assert names==section['professors_by_year'].get(src['year'][2:4],[]) and q['professors']==names
            assert q['answer']==src['answer']
            priority=bool(set(meta['current_professors']).intersection(names))
            assert q['priority']==priority
            if not priority:seen_reference=True
            else: assert not seen_reference, 'Same professor must precede references'
            year=int(re.sub(r'\D','',q['year'])[:4] or 0)
            assert year<=last_year_by_priority.get(priority,9999)
            last_year_by_priority[priority]=year
            heading=f'{q["year"]} | '+('·'.join(names) or '교수 미상')+f' | {q["number"]}번'
            assert norm(heading) in norm(doc[q['first_page']-1].get_text())
            text=''.join(doc[i-1].get_text() for i in range(q['first_page'],q['last_page']+1))
            assert norm('정답 '+src['answer']['value'] if src['answer']['status']=='source_match' else '정답 연결 확인 필요') in norm(text)
            counts['questions']+=1;counts['matched_answers']+=src['answer']['status']=='source_match'
            counts['unresolved_answers']+=src['answer']['status']!='source_match'
        expected_parts=[part for item in section['questions']+section['source_notes']+[section['answer_table_original']] for part in b.parts(item)]
        for part in expected_parts:
            actual=[p for p in meta['placements'] if p['source_page']==part['source_page'] and p['partition_clip']==part['clip']]
            if b.o.visible(source,part):
                assert actual, (key,'missing partition',part)
                rects=sorted([f.Rect(p['source_clip']) for p in actual],key=lambda r:r.y0)
                assert abs(rects[0].y0-part['clip'][1])<.01 and abs(rects[-1].y1-part['clip'][3])<.01
                assert all(abs(a.y1-z.y0)<.01 for a,z in zip(rects,rects[1:]))
                r=f.Rect(part['clip'])
                for margin in (f.Rect(r.x0,r.y0,rects[0].x0,r.y1),f.Rect(rects[0].x1,r.y0,r.x1,r.y1)):
                    if margin.width>.01: assert min(source[part['source_page']-1].get_pixmap(clip=margin,colorspace=f.csGRAY).samples, default=255)>245
            else:
                assert min(source[part['source_page']-1].get_pixmap(clip=f.Rect(part['clip']),colorspace=f.csGRAY).samples,default=255)>245
        for p in meta['placements']:
            assert not p.get('professor_table')
            dest=f.Rect(p['dest']);r=f.Rect(p['source_clip']);page=doc[p['output_page']-1]
            assert dest.y0>=129 and dest.y1<=711 and dest.x0>=41 and dest.x1<=554
            expected=f.open();ep=expected.new_page(width=595,height=842)
            ep.show_pdf_page(dest,source,p['source_page']-1,clip=r,keep_proportion=False)
            a=ep.get_pixmap(clip=dest,colorspace=f.csGRAY).samples
            z=page.get_pixmap(clip=dest,colorspace=f.csGRAY).samples
            assert len(a)==len(z)
            diff=0 if a==z else sum(abs(x-y) for x,y in zip(a,z))/len(a)
            max_diff=max(max_diff,diff);assert diff<.1,(key,'render difference',diff,p)
            # Compare the selected content text after clipping at the same position.
            assert norm(ep.get_text(clip=dest))==norm(page.get_text(clip=dest)), (key,'text changed',p)
            expected.close();regions+=1
        counts['pdfs']+=1;counts['pages']+=len(doc)
        summaries.append({'key':key,'sha256':meta['sha256'],'questions':len(meta['questions']),'pages':len(doc)})
        print('VERIFIED',meta['section_id'],len(meta['placements']),'regions',flush=True);doc.close()
    assert len(unique)==850 and sum(a['status']=='source_match' for a in unique.values())==831
    assert sum(a['status']!='source_match' for a in unique.values())==19
    result={'status':'passed',**dict(counts),'source_regions':regions,'max_mean_pixel_difference':max_diff,
            'unique_questions':len(unique),'unique_unresolved_answers':19,
            'plan_sha256':b.sha(b.HERE/'upload-plan.json'),'files':summaries}
    b.save(b.HERE/'materials-verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False))

if __name__=='__main__':main()
