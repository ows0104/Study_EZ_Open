"""Synthetic model-patch replay invariants, without medical content or models."""
import sys
from copy import deepcopy
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import round_patch as p

def case():
    bank={'questions':[{'question_id':'A','question':'Synthetic alpha'},{'question_id':'B','question':'Synthetic beta'}],'audit_summary':'old'}
    patch={'metadata':{'audit_summary':'model-authored metadata'},'question_updates':[{'question':{'question_id':'B','question':'Synthetic changed beta'},'reason':'synthetic change'}],
        'new_questions':[],'removals':[],'question_order':['B','A']}
    return bank,patch

def test_replay_preserves_unmentioned_data_exactly_and_uses_authored_order():
    bank,patch=case();before=deepcopy((bank,patch));result=p.replay(bank,patch)
    assert (bank,patch)==before and result['questions'][1]is bank['questions'][0]
    assert result['questions'][0]==patch['question_updates'][0]['question']
    assert result['audit_summary']=='model-authored metadata'

@pytest.mark.parametrize('change',['duplicate','unknown','omitted-order','remove-updated'])
def test_bad_patch_never_drops_or_silently_repairs_questions(change):
    bank,patch=case()
    if change=='duplicate':patch['question_updates']*=2
    if change=='unknown':patch['question_updates'][0]['question']['question_id']='unknown'
    if change=='omitted-order':patch['question_order']=['B']
    if change=='remove-updated':patch['removals']=[{'question_id':'B','reason':'synthetic conflict'}]
    with pytest.raises(ValueError):p.replay(bank,patch)
