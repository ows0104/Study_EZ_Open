"""Behavior registration, real creation requests and future API/UI catalog expansion."""
from __future__ import annotations

from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from tests.test_usage import seed, ADMIN, NOW_SUBJECT, NOW_RUN
from app.auth import LOCAL_TEST_USER_ID
from app.main import app
from app.database import SessionLocal
from app.routes.common import record_preview_open
from app.file_requests import FILE_PURPOSES
from app.models.previews import PREVIEW_ACTION_KINDS
from app import usage_actions as actions

checks = 0


def check(label, condition):
    global checks
    assert condition, label
    checks += 1
    print('PASS', label)


def main():
    seed()
    client = TestClient(app)
    path = f'/api/lectures/{NOW_SUBJECT}/{NOW_RUN}'
    board = lambda: client.get('/api/admin/usage', headers=ADMIN).json()
    person = lambda data: next(row for row in data['users'] if row['id'] == LOCAL_TEST_USER_ID)
    detail = lambda: client.get(f'/api/admin/usage/{LOCAL_TEST_USER_ID}', headers=ADMIN).json()
    definitions = actions.ACTIONS
    check('all file purposes have a usage action', {a.file_purpose for a in definitions if a.file_purpose} == set(FILE_PURPOSES))
    check('all preview actions have a usage action', {a.preview_kind for a in definitions if a.preview_kind} == set(PREVIEW_ACTION_KINDS))
    check('unique registered codes and valid groups', len({a.key for a in definitions}) == len(definitions)
          and all(a.group in {g['key'] for g in actions.ACTION_GROUPS} for a in definitions))
    before = person(board())
    for _ in range(2):
        response = client.post(path+'/preview-open', headers=ADMIN, json={'kind':'create'})
        check('creation-start request is recorded through the existing authenticated route', response.status_code == 204)
    current = person(board())
    check('creation attempts never become link opens or saved conversations', current['previewCreates'] == 1
          and current['opens'] == {'share':0,'mine':0} and current['previewSaves'] == 0)
    lecture = detail()['lectures'][0]
    check('each creation attempt remains visible in lifetime detail', lecture['activities']['personal_preview_create']['count'] == 2
          and bool(lecture['activities']['personal_preview_create']['lastAt']))
    check('creation does not imply quiz answers', all(current['activities'][kind]['count'] == 0
          for kind in ['pre_quiz_answer','main_quiz_answer','bank_quiz_answer']))
    for kind in ['share','mine']:
        client.post(path+'/preview-open', headers=ADMIN, json={'kind':kind})
    current = person(board())
    check('public and personal opens are independent actions', current['activities']['shared_preview_open']['count'] == 1
          and current['activities']['personal_preview_open']['count'] == 1 and current['previewCreates'] == 1)
    url='https://chatgpt.com/c/00000000-0000-0000-0000-000000000001'
    response=client.put(path+'/my-preview',headers=ADMIN,json={'provider':'chatgpt','conversationUrl':url})
    check('a saved private URL is a separate confirmation', response.status_code == 200
          and person(board())['activities']['personal_preview_saved']['count'] == 1)
    check('catalog and values never expose private URLs', url not in str(board())+str(detail()))
    data=board()
    check('every response value has its registered label and unit', set(person(data)['activities']) == {a['key'] for a in data['activityCatalog']}
          and all(a['label'] and a['summaryUnit'] and a['detailUnit'] for a in data['activityCatalog']))
    future=actions.Action('future_test_action','새 행동 테스트','personal',('previewCreates',),
                          ('previewCreates','count'),('previewCreates','lastAt'))
    with patch.object(actions,'ACTIONS',(*definitions,future)):
        expanded=board(); expanded_detail=detail()
        check('new registered actions automatically reach summary and detail catalogs',
              any(a['key']==future.key and a['label']=='새 행동 테스트' for a in expanded['activityCatalog'])
              and any(a['key']==future.key for a in expanded_detail['activityCatalog']))
        check('new registered actions automatically collect values without a second UI list',
              person(expanded)['activities'][future.key]['count']==1
              and expanded_detail['lectures'][0]['activities'][future.key]['count']==2)
    check('recording one account never changes another', next(r for r in board()['users'] if r['id']!=LOCAL_TEST_USER_ID and r['previewSaves'])['previewCreates']==0)
    def create_request(_):
        with SessionLocal() as db:
            record_preview_open(db, LOCAL_TEST_USER_ID, NOW_SUBJECT, NOW_RUN, 'create')
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(create_request,range(8)))
    check('parallel creation requests preserve every attempt',
          detail()['lectures'][0]['activities']['personal_preview_create']['count']==10)
    print(f'All {checks} usage action checks passed')


if __name__=='__main__':
    main()
