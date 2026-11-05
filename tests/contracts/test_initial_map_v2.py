import copy
import generation_v2_fixture as f
import pytest
from studyez_contracts.roots import generation_v2 as c
from studyez_contracts.roots.validate import validate_document

def full_brief():
    b=f.brief();review=f.old.document()['review']
    for k in ('concepts','relations','targets','points'):b[k]=copy.deepcopy(review[k])
    for t in b['targets']:
        for d in t['directions']:d.update(components=[{'component_id':'fact','text':'Synthetic complete fact'}],requires_visual=False)
    b['prerequisites']=[{'before_target':'T1','after_target':'T2','relation_id':'P1'}]
    return b

def test_unreviewed_initial_edge_is_valid_but_final_adoption_still_rejects_it():
    b=full_brief();r=next(r for r in b['relations']if r['relation_id']=='P1');r['review_status']='unreviewed'
    assert c.validate_brief(b)==b and not c.brief_findings(b)
    doc=f.old.document();doc['prerequisites']=b['prerequisites']
    next(r for r in doc['review']['relations']if r['relation_id']=='P1')['review_status']='unreviewed'
    with pytest.raises(ValueError,match='reviewed relation'):validate_document(doc)
    assert r['review_status']=='unreviewed'

@pytest.mark.parametrize('bad',['association','comparison','from','to','unknown_target','cycle'])
def test_initial_edge_semantics_are_never_relaxed(bad):
    b=full_brief();r=next(r for r in b['relations']if r['relation_id']=='P1')
    if bad in('association','comparison'):r['kind']=bad
    elif bad=='from':r['from_id']='D'
    elif bad=='to':r['to_id']='D'
    elif bad=='unknown_target':b['prerequisites'][0]['before_target']='unknown'
    else:
        back={**copy.deepcopy(r),'relation_id':'P_BACK','from_id':'C','to_id':'A'}
        b['relations'].append(back);b['prerequisites'].append({'before_target':'T2','after_target':'T1','relation_id':'P_BACK'})
    assert c.brief_findings(b)
    with pytest.raises(ValueError):c.validate_brief(b)

def test_initial_correction_preserves_raw_point_scope_and_cannot_claim_independence():
    before=full_brief();before['prerequisites'][0]['relation_id']='R1';after=full_brief()
    after['provenance']['independent_points']='derived';c.validate_initial_correction(before,after,'Synthetic structural correction')
    bad=copy.deepcopy(after);bad['points'][0]['text']='Changed original point'
    with pytest.raises(ValueError,match='point text'):c.validate_initial_correction(before,bad,'Cannot rewrite original')
    after['provenance']['independent_points']='confirmed'
    with pytest.raises(ValueError,match='derived'):c.validate_initial_correction(before,after,'Still question-informed')

def test_dangling_point_targets_and_duplicate_ids_are_retained_as_findings():
    b=full_brief();b['points'][0]['target_ids']=['missing']
    assert c.brief_findings(b)
    b=full_brief();duplicate=copy.deepcopy(b['targets'][0]);duplicate['title']='Another synthetic target';b['targets'].append(duplicate)
    assert c.brief_findings(b)
