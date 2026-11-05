"""Test technical metadata normalization using synthetic nodes only."""
import sys
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parent))
import recover_completed_map as r

def test_only_authored_opposite_classification_is_oriented_by_existing_parentage():
    b={'concepts':[{'concept_id':'A','parent_ids':[]},{'concept_id':'B','parent_ids':['A']},{'concept_id':'C','parent_ids':[]}],
        'relations':[{'relation_id':'R1','from_id':'A','to_id':'B','kind':'classification','condition':'Synthetic category','review_status':'reviewed'},
            {'relation_id':'R2','from_id':'B','to_id':'A','kind':'classification','condition':'Synthetic detailed fact','review_status':'reviewed'},
            {'relation_id':'R3','from_id':'C','to_id':'B','kind':'classification','condition':'Synthetic cross-link','review_status':'reviewed'}],
        'targets':[],'prerequisites':[],'points':[{'point_id':'P','text':'Synthetic point'}]}
    before=deepcopy(b);value,changes,rejected=r.normalize_classification_orientation(b)
    assert b==before and len(changes)==1 and not rejected
    assert changes[0]['relation_id']=='R2'and changes[0]['authoredAncestorPath']==['B','A']
    assert value['relations'][1]=={**b['relations'][1],'from_id':'A','to_id':'B'}
    assert value['relations'][2]==b['relations'][2]and value['points']==b['points']

def test_invalid_dependency_proposal_is_archived_without_inventing_a_prerequisite():
    b={'concepts':[{'concept_id':'A','parent_ids':[]},{'concept_id':'B','parent_ids':[]}],
        'relations':[{'relation_id':'R','from_id':'A','to_id':'B','kind':'comparison','condition':'Synthetic comparison','review_status':'reviewed'}],
        'targets':[{'target_id':'T1','concept_ids':['A']},{'target_id':'T2','concept_ids':['B']}],
        'prerequisites':[{'before_target':'T1','after_target':'T2','relation_id':'R'}]}
    value,_,rejected=r.normalize_classification_orientation(b)
    assert not value['prerequisites']and rejected[0]['proposal']==b['prerequisites'][0]
    assert value['relations']==b['relations']
