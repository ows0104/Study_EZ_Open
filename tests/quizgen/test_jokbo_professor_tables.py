from dataclasses import asdict

import fitz

from quizgen import jokbo as J
from quizgen.repair_professors import repair_payload, content_digest, signature


def test_dense_table_keeps_neighbor_rows_and_sitting_columns_separate():
    doc = fitz.open()
    page = doc.new_page(width=700, height=500)
    def put(x, y, text):
        page.insert_text((x, y), text, fontname='korea', fontsize=9)
    put(50, 35, '교수님 목록')
    for x, text in [(65,'수업제목'), (300,'20'), (380,'19'), (460,'16-2'), (540,'16-1')]:
        put(x, 60, text)
    for y, key, title, names in [
        (90,'16','중추 신경계', ['김혜선']*4),
        (103,'17-18','체액 전해질', ['신현우','박종완','박종완','박종완']),
        (116,'19-20','순환기 약리', ['조정현','박종완','정재용','유경상']),
    ]:
        put(40,y,key);put(100,y,title)
        for x, name in zip([300,380,460,540],names):put(x,y,name)
    put(40,145,'문제 출처');put(300,145,'학습부')
    lectures, profs, warning = J.parse_toc(doc)
    assert [k for k,_ in lectures] == ['16','17-18','19-20']
    assert profs['17-18'] == {'20':['신현우'],'19':['박종완'],'16-2':['박종완'],'16-1':['박종완']}
    assert profs['19-20']['16-2'] == ['정재용']
    assert profs['19-20']['16-1'] == ['유경상']
    assert warning is None
    assert all('학습부' not in cell for row in profs.values() for cell in row.values())


def test_exact_sitting_is_used_in_merge_and_professor_priority():
    old = J.Section(lecture_key='17-18', title='체액 전해질')
    old.questions = [J.Question(year=y,no='1',stem='문항 '+y) for y in ['2016-1','2016-2']]
    main = J.Section(lecture_key='17-18',title='체액 전해질')
    tables = {'17-18': {'16-1':['박종완'],'16-2':['신현우']}}
    profs = {}
    J.merge_older([main],[('17-18','체액 전해질')],profs,{'sections':[old],'profs':tables},0)
    assert {q.year:q.by for q in main.questions} == {'2016-1':['박종완'],'2016-2':['신현우']}
    payload = {'lecture_key':'17-18','title':'체액 전해질','may_contain':[],
               'questions':[asdict(q) for q in main.questions], 'stats':{'professors_by_year':tables['17-18']}}
    _, note = J.split_by_professor(payload,['박종완'])
    assert note['own_years'] == ['2016-1']
    assert J.year_professors(tables['17-18'],'2016') == []
    assert J.year_professors({'16-1':['박종완']},'2016') == []
    assert J.year_professors({'16':['박종완']},'2016-2') == ['박종완']


def test_saved_question_text_is_preserved_while_author_metadata_is_repaired():
    q = asdict(J.Question(year='2016-1',no='1',stem='저장된 문제',src=0,by=[]))
    raw = {'lecture_key':'17-18','title':'체액 전해질','may_contain':[],
           'questions':[q],'stats':{'professors_by_year':{},'repeat_rate':0}}
    repaired, count = repair_payload(raw, {'17-18':{'16-1':['박종완']}}, {0:{signature(q):['박종완']}})
    assert count == 1 and repaired['questions'][0]['by'] == ['박종완']
    assert raw['questions'][0]['by'] == []
    assert content_digest(raw) == content_digest(repaired)


def test_2022_history_uses_verified_notes_and_does_not_change_other_lectures_or_years():
    from quizgen.professor_history import corrected_payload
    raw = {'lecture_key':'17-18','title':'체액 및 전해질 조절 (1)~(2)','may_contain':[],
           'stats':{'professors_by_year':{'22':['신현우'],'21':['신현우']}},
           'questions':[asdict(J.Question(year=y,no='1',stem='문항 '+y,by=['신현우'])) for y in ['2022','2021']]}
    fixed=corrected_payload(raw)
    assert fixed['stats']['professors_by_year']=={'22':['박종완'],'21':['신현우']}
    assert fixed['questions'][0]['by']==['박종완']
    assert fixed['questions'][1]['by']==['신현우']
    assert content_digest(raw)==content_digest(fixed)
    assert corrected_payload(fixed)==fixed
    _, note=J.split_by_professor(raw,['박종완'])
    assert note['own_years']==['2022'] and note['reference'][0]['year']=='2021'
    unrelated={**raw,'title':'기타항생제'}
    assert corrected_payload(unrelated)==unrelated
    stats=J.repeat_stats(section_for_test(raw),{'17-18':raw['stats']['professors_by_year']})
    assert stats['professors_by_year']['22']==['박종완']
    md=J.to_markdown(section_for_test(fixed),stats)
    assert '2022년 박종완' in md and 'p.1, p.26' in md


def section_for_test(payload):
    from quizgen.repair_professors import section
    return section(payload)
