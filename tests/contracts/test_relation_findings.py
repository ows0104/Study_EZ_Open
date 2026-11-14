"""A: the map's content relations (docs/changes/2026-11-14-map-relation-guard)."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generation_v2_fixture as f
from studyez_contracts.roots import generation_v4 as v4


def goals(brief):
    return [d['direction_id'] for t in brief['targets'] for d in t['directions']]


def test_a_map_whose_goals_each_have_their_own_content_relation_has_no_finding():
    assert v4.relation_findings(f.brief()) == []
    assert v4.relation_defect_share(f.brief()) == 0.0


def test_a_goal_with_only_hierarchy_relations_is_a_finding():
    b = f.brief()
    next(r for r in b['relations'] if r['relation_id'] == 'R2')['kind'] = 'classification'
    found = v4.relation_findings(b)
    assert len(found) == 1 and found[0].startswith('D2: 계층(classification) 관계만 있다')
    assert v4.relation_defect_share(b) == 0.5


def test_goals_sharing_one_content_relation_set_are_findings_from_four_on():
    b = f.brief()
    t = b['targets'][0]
    base = t['directions'][0]
    # three goals on R1 alone: not yet a finding (the other 33 runs of 2026-11-14 never share a set at all)
    t['directions'] = [base, *[{**copy.deepcopy(base), 'direction_id': f'D1{k}'} for k in 'ab'], t['directions'][1]]
    assert v4.relation_findings(b) == []
    t['directions'].insert(1, {**copy.deepcopy(base), 'direction_id': 'D1c'})
    found = v4.relation_findings(b)
    assert [x.split(':')[0] for x in found] == ['D1', 'D1c', 'D1a', 'D1b']
    assert all('다른 방향 3개' in x for x in found)
    assert v4.relation_defect_share(b) == 4 / 5


def test_the_finding_leaves_the_brief_unchanged():
    b = f.brief()
    next(r for r in b['relations'] if r['relation_id'] == 'R2')['kind'] = 'classification'
    before = copy.deepcopy(b)
    v4.relation_findings(b)
    assert b == before
