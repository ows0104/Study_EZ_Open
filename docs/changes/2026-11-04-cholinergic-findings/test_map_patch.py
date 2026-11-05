"""Synthetic source-map replay checks; no course content or model."""
import sys
from copy import deepcopy
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import map_patch as p

def case():
    previous={'concepts':[{'concept_id':'A','label':'Synthetic A'}],'relations':[{'relation_id':'R','condition':'Synthetic relation'}],
        'targets':[{'target_id':'T','title':'Synthetic target'}],'points':[{'point_id':'P','text':'Synthetic point'}],
        'provenance':{'method':'synthetic old'},'scope':{'label':'synthetic scope'},'prerequisites':[],
        'sources':[{'source_id':'S1'}],'exclusions':[{'point_id':'X'}]}
    patch={'concepts':[{'concept_id':'B','label':'Synthetic B'}],'relations':[],
        'targets':[{'target_id':'T','title':'Synthetic refined target'}],'points':[],
        'provenance':{'method':'synthetic source-only correction'},'scope':{'label':'synthetic scope'},'prerequisites':[],'reasons':['synthetic correction']}
    return previous,patch

def test_map_delta_preserves_untouched_source_points_and_exclusions():
    previous,patch=case();before=deepcopy((previous,patch));value=p.replay(previous,patch)
    assert (previous,patch)==before and value['points']==previous['points']
    assert value['sources']==previous['sources'] and value['exclusions']==previous['exclusions']
    assert [c['concept_id']for c in value['concepts']]==['A','B']
    assert value['targets'][0]==patch['targets'][0]

def test_duplicate_authored_map_updates_are_rejected():
    previous,patch=case();patch['targets']*=2
    with pytest.raises(ValueError,match='Duplicate map'):p.replay(previous,patch)
