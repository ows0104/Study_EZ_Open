from copy import deepcopy
import pytest
import automation_fixture as f
from studyez_contracts.roots.automation import validate_result, validate_brief, make_document


def test_full_result_and_timestamp_independence():
    packet=f.packet();result=f.result(packet)
    result['validation']['checked_at']='previous checking time'
    doc=validate_result(result,packet)
    assert len(doc['tasks'])==2 and len(doc['adopted_target_ids'])==1


@pytest.mark.parametrize('change', ['bank','source','points','verdict','budget','stage','proof','validation','revision','provenance'])
def test_consumer_rejects_altered_evidence(change):
    packet=f.packet();value=f.result(packet)
    if change=='bank':value['document']['bank_snapshot']['questions'][0]['answer']='changed'
    if change=='source':value['brief']['sources'][0]['sha256']='f'*64
    if change=='points':value['sourceAudit']['review']['points']=[]
    if change=='verdict':value['medical']['reviews'].pop()
    if change=='budget':value['manifest']['repairRounds']=4
    if change=='stage':value['manifest']['stages'][0]['status']='started'
    if change=='proof':value['manifest']['stages'][0]['outputHash']='e'*64
    if change=='validation':value['validation']['pass']=not value['validation']['pass']
    if change=='revision':value['document']['revision']='unrelated'
    if change=='provenance':value['brief']['provenance']['independent_points']='confirmed'
    with pytest.raises(ValueError):validate_result(value,packet)


def test_unconfirmed_direction_never_becomes_task_and_target_is_preserved():
    brief=f.brief();bank=f.bank();audit=f.audit(brief,bank)
    coverage=audit['review']['coverage'][0]
    coverage.update(status='partial',confirmed_direction_ids=['D1'],unknown_direction_ids=['D2'])
    audit['review']['mappings']=audit['review']['mappings'][:1]
    doc=make_document(brief,bank,audit,revision='v',title='t',exam_date=None)
    assert len(doc['tasks'])==1 and doc['adopted_target_ids']==['T1']


def test_provided_relation_is_not_tested():
    brief=f.brief();bank=f.bank();audit=f.audit(brief,bank)
    audit['review']['mappings'][0].update(tested_relation_ids=[],provided_relation_ids=['R1'])
    with pytest.raises(ValueError):make_document(brief,bank,audit,revision='v',title='t',exam_date=None)


@pytest.mark.parametrize('field,value',[('manifest',[]),('validation',None),('document',[]),('stages',[None])])
def test_malformed_envelopes_are_validation_errors(field,value):
    packet=f.packet();result=f.result(packet)
    if field=='stages':result['manifest']['stages']=value
    else:result[field]=value
    with pytest.raises(ValueError):validate_result(result,packet)


def test_source_only_claim_needs_empty_supplied_inputs_and_intake_identity():
    from studyez_contracts.roots.automation import packet_hash
    from studyez_contracts.roots import document_hash
    packet=f.packet();packet.update(authoring='web',inputMode='source',conceptMap='',points='')
    packet['webResponse']=f.web_response(packet['generationId']);packet['webResponseHash']=document_hash(packet['webResponse'])
    packet['inputHash']=packet_hash(packet)
    result=f.result(packet);validate_result(result,packet)
    wrong=deepcopy(result);wrong['manifest']['sourceIntakeHash']='f'*64
    with pytest.raises(ValueError):validate_result(wrong,packet)
    packet['points']='Provided point'
    with pytest.raises(ValueError):validate_result(result,packet)
