import copy
import hashlib
import json
from pathlib import Path
import pytest
from studyez_contracts.bank import authored_json as c
from studyez_contracts.bank import response_file
from studyez_contracts.bank.schema import schema_errors
from studyez_contracts.bank.professors import from_sources

FIXTURE = Path(__file__).parents[1] / 'fixtures/bank-file-valid.json'
RAW = FIXTURE.read_text(encoding='utf-8')
NAME = 'study-ez-261006_02-bank.json'


def test_all_formats_preserve_content_and_compile_without_a_model():
    doc = c.loads(RAW)
    bank, evidence = c.to_bank(RAW, 'Synthetic lecture')
    assert schema_errors(bank) == []
    assert [q['question_id'] for q in bank['questions']] == doc['question_ids']
    assert bank['questions'][0]['tier'] == 'Essential'
    assert bank['questions'][1]['question'] == 'Before {{c1}}, after {{c1}}, repeated {{c1}}.'
    assert bank['questions'][1]['answer_units'] == ['A', 'B', 'A']
    assert bank['questions'][2]['answer_units'] == ['A, first', 'B']
    assert bank['questions'][4]['answer_units'] == ['Target A']
    assert bank['questions'][4]['correct_option_ids'] == ['B']
    assert bank['questions'][5]['answer_units'] == ['First','Second']
    assert bank['source_conflicts'] == doc['source_conflicts']
    assert evidence['Q006']['evidence'] == doc['questions'][5]['evidence']
    mutated = copy.deepcopy(bank)
    mutated['questions'][0]['question'] = 'Model rewrite'
    mutated['questions'][0]['concept_id'] = 'C1'
    restored = c.preserve_authored(mutated, RAW, 'Synthetic lecture')
    assert restored['questions'][0]['question'] == doc['questions'][0]['question']
    assert restored['questions'][0]['concept_id'] == 'C1'


@pytest.mark.parametrize('path,value', [
    (['complete'],False), (['schema_version'],True), (['question_count'],5),
    (['question_ids'],['Q001']), (['questions',0,'question_id'],'Q002'),
    (['questions',0,'importance'],4), (['questions',0,'advanced'],'false'),
    (['questions',0,'unexpected'],'value'), (['questions',0,'answers'],[]),
    (['questions',1,'question'],'Bad {{A}}'), (['questions',1,'answers'],['A']),
    (['questions',3,'explanation'],''), (['questions',3,'conflict_id'],'CF999'),
    (['questions',4,'answers'],['Z']), (['questions',4,'mcq_mode'],'none'),
    (['questions',4,'options',1,'id'],'A'), (['questions',0,'evidence','slides'],[]),
    (['questions',0,'evidence','slides',0,'page'],True), (['conflict_ids'],[]),
    (['source_conflicts',0,'unresolved'],'false'), (['prompt_version'],'1.79'),
])
def test_rejects_broken_transport(path,value):
    doc = json.loads(RAW); cursor=doc
    for key in path[:-1]: cursor=cursor[key]
    cursor[path[-1]]=value
    with pytest.raises(ValueError): c.loads(json.dumps(doc))


def test_fingerprint_identity_and_legacy_dispatch():
    raw='\ufeff'+RAW.replace('\n','\r\n')
    info=response_file.validate(raw,NAME,'약리학','261006_02')
    assert info['sha256']==hashlib.sha256(raw.encode()).hexdigest()
    assert info['byteLength']==len(raw.encode())
    assert response_file.metadata(raw)['generation_id']=='ab682837b3c34916a2c0c77c342bd115'
    with pytest.raises(ValueError): response_file.validate(raw,NAME,'other','261006_02')
    with pytest.raises(ValueError): response_file.validate(raw,NAME,'약리학','261006_02',{'sha256':'bad','byteLength':1})
    legacy=FIXTURE.with_suffix('.md').read_text(encoding='utf-8')
    assert response_file.validate(legacy,NAME.replace('.json','.md'),'약리학','261006_02')['questionCount']==8
    with pytest.raises(ValueError): response_file.validate(legacy.replace('1.76','1.80'),NAME.replace('.json','.md'),'약리학','261006_02')
    for bad in [RAW+'\nSTUDYEZ_BANK_COMPLETE','```json\n'+RAW+'\n```',RAW.replace('"complete": true','"complete": true,"complete": true'),RAW.replace('"importance":5','"importance":NaN',1)]:
        with pytest.raises(ValueError): c.loads(bad)


def test_note_writer_is_never_used_as_professor():
    def names(filename): return from_sources([{'kind':'notes_current','filename':filename}])
    assert names('[261105_07] 심내막염, 중추신경계감염_서윤성v1.pdf')==[]
    assert names('[261007_01] 내분비 약리 기초 (조정현)_황다현v1.pdf')==['조정현']
    assert names('[261007_01] 강의(1)(고지원·김혜령)_필기자v1.pdf')==['고지원','김혜령']
