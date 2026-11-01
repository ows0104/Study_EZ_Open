"""Export concise, professor-prioritized vector PDFs from immutable management JSON."""
from pathlib import Path
import hashlib, importlib.util, json, re, sys
import pymupdf as f

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PACKAGE = ROOT / 'output/materials/감염과 면역_2026_JSON'
OUT = ROOT / 'output/pdf/감염과 면역_2026_교수우선_v2'
BASE = HERE.parent / '2026-11-01-infection-jokbo-answer-audit'
spec = importlib.util.spec_from_file_location('retained_layout', BASE / 'organize.py')
o = importlib.util.module_from_spec(spec); spec.loader.exec_module(o)
sys.path.insert(0, str(ROOT))
from runner.filenames import parse

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path, data): Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def parts(item): return [{'source_page': r['source_page'], 'clip': r['bbox']} for r in item['source_regions']]

def timetable_names(values):
    # CBL timetable cells also contain division labels, e.g. '(분반) A: 문송미'.
    return sorted({name for value in values for name in re.findall(r'[가-힣]{2,4}', value.replace('(분반)', ''))
                   if name not in ('교수', '교수님', '미정')})

def authors(section, q):
    year = q['year']
    names = section['professors_by_year'].get(year[2:4], []) if re.match(r'^20\d{2}', year) else []
    assert names == q['professors_from_source_table'], q['id']
    return names

def ordered(section, current):
    return sorted(section['questions'], key=lambda q: (
        0 if set(authors(section, q)) & set(current) else 1,
        -int(re.sub(r'\D', '', q['year'])[:4] or 0),
        q['year'], q['source_order']))

def make(section, current, how, source):
    placements = []; records = []; doc = f.open(); toc = []
    title = section['title']
    def base(doc, heading, small=''):
        p = doc.new_page(width=595, height=842)
        o.txt(p, (42, 22, 553, 63), '감염과 면역 | '+title, 12, o.BLUE)
        o.txt(p, (42, 67, 553, 93), heading, 15, o.BLUE)
        o.txt(p, (42, 98, 553, 120), small, 9, o.GREY)
        p.draw_line((42, 121), (553, 121), color=(.78,.82,.86), width=.6)
        o.txt(p, (42, 802, 520, 825), '정답: 원본 표기 기준 | '+('우선순위: 올해 필기 파일명' if how == 'notes_current' else '우선순위: 올해 시간표 기준'), 8, o.GREY)
        o.txt(p, (523, 802, 553, 825), str(len(doc)), 9, o.GREY)
        return p
    o.base = base
    last_group = last_year = None
    for q in ordered(section, current):
        names = authors(section, q)
        priority = bool(set(names) & set(current))
        label = '같은 교수 기출 우선' if priority else '참고 기출'
        who = '·'.join(names) or '교수 미상'
        heading = f'{q["year"]} | {who} | {q["number"]}번'
        pages = sorted({r['source_page'] for r in q['source_regions']})
        answer = q['answer']
        footer = '정답 '+answer['value'] if answer['status'] == 'source_match' else '정답 연결 확인 필요'
        start = len(doc)+1
        first = o.place(doc, source, parts(q), heading, label+' | 원본 p.'+','.join(map(str,pages)), footer, placements)
        assert first == start, q['id']
        if last_group != label: toc.append([1,label,first]); last_group=label; last_year=None
        year_label=q['year']+' | '+who
        if last_year != year_label: toc.append([2,year_label,first]);last_year=year_label
        toc.append([3,str(q['number'])+'번',first])
        records.append({'id':q['id'],'year':q['year'],'number':q['number'],'professors':names,
                        'priority':priority,'answer':answer,'first_page':first,'last_page':len(doc)})
    question_pages=len(doc)
    reference=[p for note in section['source_notes'] for p in parts(note)]
    first=o.place(doc,source,reference,'공용 자료','원본 안내·공용 자료','',placements)
    if first:toc.append([1,'원본 안내·공용 자료',first])
    first=o.place(doc,source,parts(section['answer_table_original']),'원본 정답표','','',placements)
    if first:toc.append([1,'원본 정답표',first])
    doc.set_toc(toc); doc.subset_fonts()
    for p in placements:
        doc[p['output_page']-1].show_pdf_page(f.Rect(p['dest']), source, p['source_page']-1,
                                           clip=f.Rect(p['source_clip']), keep_proportion=False)
    suffix='-'+'-'.join(current) if current else '-교수미상'
    path=OUT/f'2026-{section["id"]}-족보{suffix}.pdf'
    doc.save(path,garbage=3,deflate=True); count=len(doc);doc.close()
    return {'section_id':section['id'],'title':title,'path':str(path),'sha256':sha(path),'pages':count,
            'current_professors':current,'professor_basis':how,'question_pages':question_pages,
            'questions':records,'placements':placements}

def main():
    assert not OUT.exists(), 'Never overwrite an earlier export'
    OUT.mkdir(parents=True)
    catalog=read(PACKAGE/'catalog.json'); old=read(BASE/'upload-plan.json'); before=read(HERE/'remote-before.json')
    source_path=PACKAGE/catalog['source']['file']; assert sha(source_path)==catalog['source']['sha256']
    source=f.open(source_path); files={}; lectures=[]; inputs={}
    for entry in catalog['sections']:
        path=PACKAGE/entry['json_file'];section=read(path);inputs[str(path)]=sha(path)
        targets=[r for r in catalog['lectures'] if r['section_id']==section['id']]
        for target in targets:
            current=timetable_names(target['lecture']['professors']);how='timetable'
            notes=[a for a in before['assets'] if a['run_id']==target['run_id'] and a['kind']=='notes_current']
            if notes:
                assert len(notes)==1
                parsed=parse(Path(notes[0]['filename']))
                current=list(parsed.professors) if parsed else []; how='notes_current'
            current=sorted(set(current));key=section['id']+'|'+'·'.join(current)+'|'+how
            if key not in files:
                files[key]=make(section,current,how,source)
                print('PREPARED',section['id'],len(files[key]['questions']),'questions',files[key]['pages'],'pages',flush=True)
            lectures.append({'run_id':target['run_id'],'section_id':section['id'],'file_key':key,'path':files[key]['path']})
    save(HERE/'upload-plan.json',{'subject':catalog['subject'],'source':catalog['source'],'source_path':str(source_path),
         'inputs':{**inputs,str(PACKAGE/'catalog.json'):sha(PACKAGE/'catalog.json'),str(BASE/'upload-plan.json'):sha(BASE/'upload-plan.json')},
         'files':files,'lectures':lectures,'previous_plan':str(BASE/'upload-plan.json')})
    print('DONE',len(files),'PDFs',len(lectures),'lecture attachments')

if __name__=='__main__':main()
