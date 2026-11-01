"""Publish only the approved, verified organized exam attachments."""
from pathlib import Path
import dataclasses,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from runner import ahead,publish
from runner.cycle import runner_token

plan=json.loads((HERE/'upload-plan.json').read_text(encoding='utf-8'))
v=json.loads((HERE/'materials-verification.json').read_text(encoding='utf-8'))
assert v['status']=='passed'
assert hashlib.sha256((HERE/'upload-plan.json').read_bytes()).hexdigest()==v['plan_sha256']
assert (HERE/'visual-review.json').exists()
assert json.loads((HERE/'visual-review.json').read_text(encoding='utf-8'))['status']=='passed'
before=json.loads((HERE/'remote-before.json').read_text(encoding='utf-8'))
assert {r['run_id'] for r in plan['lectures']}=={r['run_id'] for r in before['lectures']}
for item in plan['files'].values():assert hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==item['sha256']
cells={c.key:c for c in ahead.read_cells(ROOT/'data/timetable/2026_본1_2학기_시간표.json')}
client=publish.Client(publish.DEFAULT_API_BASE,runner_token(None),timeout=180)
ledger=publish.load_ledger(ROOT/'runs',client.base)
report=publish.Report(lectures=80,linked=80)
with (HERE/'upload.log').open('a',encoding='utf-8') as handle:
    def log(message):
        print(message,flush=True);handle.write(message+'\n');handle.flush()
    for row in plan['lectures']:
        if row['section'] not in plan['corrected_sections']:continue
        item=cells[row['run_id']].as_lecture()
        lecture=publish.LecturePlan(subject=plan['subject'],run_id=row['run_id'],item=item,ahead=True,
                                   uploads=[publish.Upload('jokbo',Path(row['path']))])
        try:publish._publish_one(lecture,client,ledger,report,force=False,log=log)
        except Exception as error:
            report.failures.append(f'{row["run_id"]}: {type(error).__name__}: {error}');log(report.failures[-1])
        finally:publish.save_ledger(ROOT/'runs',client.base,ledger)
    result={**dataclasses.asdict(report),'plan_sha256':v['plan_sha256']}
    (HERE/'upload-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    log(json.dumps(result,ensure_ascii=False));assert not report.failures,result
