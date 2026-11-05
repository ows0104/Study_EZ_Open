"""Read only the authorized pilot's state; never print credentials or response content."""
import json
from datetime import datetime,UTC
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy import create_engine,text
ROOT=Path(__file__).resolve().parents[3]
url=dotenv_values(ROOT/'server/.env')['DATABASE_URL']
for prefix in ('postgres://','postgresql://'):
    if url.startswith(prefix):url='postgresql+psycopg://'+url[len(prefix):];break
engine=create_engine(url,connect_args={'prepare_threshold':None})
with engine.connect()as conn:
    conn.execute(text('SET TRANSACTION READ ONLY'))
    row=conn.execute(text('''SELECT r.id,r.job_id,r.packet,r.result_digest,
      (r.web_dispatch IS NOT NULL) AS dispatched,(r.web_response IS NOT NULL) AS received,
      j.state,j.stage,j.message FROM root_generation r JOIN prequiz_job j ON j.id=r.job_id
      WHERE r.subject=:subject AND r.run_id=:run ORDER BY r.created_at DESC LIMIT 1'''),{'subject':'감염과 면역','run':'261102_03'}).mappings().first()
    banks=conn.execute(text('SELECT subject,run_id,build_id,status,open_to_students FROM quiz_bank WHERE run_id IN (:pilot,:old)'),{'pilot':'261102_03','old':'261002_01'}).mappings().all()
    result={'at':datetime.now(UTC).isoformat(),'banks':[dict(r)for r in banks],'dataWrites':False}
    if row:
        p=row['packet'];result['generation']={k:row[k]for k in('id','job_id','dispatched','received','state','stage','message')}
        result['generation'].update(published=bool(row['result_digest']),policy=p.get('sourceAssessmentFormat'),privatePilot=p.get('privatePilot'),inputHash=p.get('inputHash'),sources=[{k:s[k]for k in('id','filename','sha256','sizeBytes')}for s in p['sources']])
    else:result['generation']=None
    conn.rollback()
engine.dispose()
out=ROOT/'runs/_development/2026-11-05-root-pipeline-deploy/probes';out.mkdir(parents=True,exist_ok=True)
(out/(datetime.now(UTC).strftime('%Y%m%dT%H%M%S')+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
