"""Reviewed learning positions survive real single/batch HTTP selection and ratings."""
import copy,datetime
from unittest.mock import patch
from tests.test_bank import STUDENT
from tests.test_question_order import make_bank,NOW
from fastapi.testclient import TestClient
from app.auth import get_current_user
from app.database import Base,SessionLocal,engine
from app.main import app
from app.models import Lecture,QuizBank,BankState


def main():
    Base.metadata.create_all(engine)
    bank=make_bank([('comparison','overview','discrimination',5,['anticoag','lysis']),
                    ('overview','overview','direct',5,[]),('middle','other','direct',12,[]),
                    ('anticoag','heparin','mechanism',18,[]),('lysis','tpa','mechanism',26,[])])
    for q in bank['questions']:q['learning_page']=int(q['source_refs'][0]['locator'][2:])
    bank['questions'][0]['learning_page']=26
    bank['questions'][0]['source_refs'].append({'source_id':'S1','locator':'p.26'})
    original=copy.deepcopy(bank)
    with SessionLocal() as db:
        for rid in ('single','batch'):
            db.add(Lecture(subject='reviewed-order',run_id=rid,uid='reviewed-order-'+rid,
                title='검토된 학습 위치',date=datetime.date(2026,10,18),slot=1,slot_end=1,start_time='09:00'))
            db.flush()
            db.add(QuizBank(subject='reviewed-order',run_id=rid,build_id='retained',bank=bank,
                validation={'pass':True},pages={'comparison':[5,26,28]},open_to_students=True))
        db.commit()
    app.dependency_overrides[get_current_user]=lambda:STUDENT
    client=TestClient(app)
    def post(url,data=None):
        response=client.post(url,json=data or {})
        assert response.status_code==200,response.text
        return response.json()
    with patch('app.routes.bank.engine.now_ms',return_value=NOW):
        for rid in ('single','batch'):
            base='/api/lectures/reviewed-order/'+rid+'/bank'
            selection={'lectures':[{'subject':'reviewed-order','runId':rid}]}
            seen=[]
            for expected in ('overview','middle','anticoag','lysis','comparison'):
                pick=post('/api/bank/batch/next',selection) if rid=='batch' else post(base+'/next')
                assert pick['question']['question_id']==expected,(rid,expected,pick['question'])
                seen.append(expected)
                post(base+'/reveal',{'reviewToken':pick['reviewToken']})
                post(base+'/rate',{'reviewToken':pick['reviewToken'],'rating':'Again'})
            with SessionLocal() as db:
                row=db.get(QuizBank,('reviewed-order',rid))
                saved=db.get(BankState,(STUDENT.id,'reviewed-order',rid))
                assert row.bank==original and row.build_id==saved.build_id=='retained'
                assert [h['question_id'] for h in saved.state['history']]==seen
                assert all(h['rating']=='Again' for h in saved.state['history'])
    print('PASS: HTTP single/batch respect actual learning pages and cross-concept prerequisites; '
          'all Again progresses once; evidence, bank and build preserved')


if __name__=='__main__':main()
