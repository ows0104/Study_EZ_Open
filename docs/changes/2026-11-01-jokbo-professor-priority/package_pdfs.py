"""Package the verified PDFs and a concise lecture-to-file index."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
plan=json.loads((HERE/'upload-plan.json').read_text(encoding='utf-8'))
check=json.loads((HERE/'materials-verification.json').read_text(encoding='utf-8'))
assert check['status']=='passed' and check['plan_sha256']==hashlib.sha256((HERE/'upload-plan.json').read_bytes()).hexdigest()
target=ROOT/'output/materials/감염과 면역_2026_교수우선_PDF.zip';assert not target.exists()
entries={Path(m['path']).name:Path(m['path']) for m in plan['files'].values()}
assert len(entries)==len(plan['files'])==74
mapping=[]
for row in sorted(plan['lectures'],key=lambda r:r['run_id']):
    meta=plan['files'][row['file_key']]
    mapping.append(f'{row["run_id"]} | {meta["title"]} | 올해 담당 {"·".join(meta["current_professors"]) or "미상"} | {Path(row["path"]).name}')
listing='69단원 / 80강의 / 교수 구성별 74개 PDF\n같은 교수 기출 우선, 그다음 참고 기출. 연도·교수·번호는 각 문항 위에 표시합니다.\n올해 필기가 아직 없어 현재 정렬은 시간표 기준입니다. 복습 출제 시 실제 올해 필기 파일명으로 재확인합니다.\n정답은 원본 표기 기준이며 연결 확인 필요 19건은 보존했습니다.\n\n'+'\n'.join(mapping)+'\n'
with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as z:
    for name,path in sorted(entries.items()):z.write(path,'족보/'+name)
    z.writestr('수업별_첨부목록.txt',listing.encode('utf-8'))
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    for name,path in entries.items():assert hashlib.sha256(z.read('족보/'+name)).digest()==hashlib.sha256(path.read_bytes()).digest()
result={'status':'passed','path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'pdfs':74,'lecture_links':80}
(HERE/'package-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
