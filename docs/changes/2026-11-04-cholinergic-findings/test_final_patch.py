"""Synthetic guards for the single model-authored direction-reference correction."""
import sys
from pathlib import Path
from copy import deepcopy
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import final_patch as p

def case():
    brief={'targets':[{'target_id':'T','directions':[{'direction_id':'D24','cue':'Synthetic cue','answer_scope':'Synthetic answer','relation_ids':['R1','R2'],'requirement':'required'},
        {'direction_id':'other','cue':'Other cue','answer_scope':'Other answer','relation_ids':['R2'],'requirement':'required'}]}],
        'points':[{'text':'Unchanged synthetic source point'}]}
    return brief,{'direction_id':'D24','expected_relation_ids':['R1','R2'],'relation_ids':['R1'],'reason':'Synthetic provided relation'}

def test_only_binding_changes_and_the_required_fact_remains_elsewhere():
    brief,fix=case();before=deepcopy(brief);value=p.apply_refs(brief,[fix])
    assert brief==before and value['points']==before['points']
    assert value['targets'][0]['directions'][0]=={**before['targets'][0]['directions'][0],'relation_ids':['R1']}
    assert value['targets'][0]['directions'][1]==before['targets'][0]['directions'][1]

def test_a_reference_fix_cannot_erase_the_only_required_recall_of_a_fact():
    brief,fix=case();brief['targets'][0]['directions'].pop()
    with pytest.raises(ValueError,match='erase a required fact'):p.apply_refs(brief,[fix])
