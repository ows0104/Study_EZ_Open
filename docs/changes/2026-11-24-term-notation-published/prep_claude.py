"""Claude 검토용 입력: <runId>/claude/questions-<n>.json(원본 공개판 글, scan과 같은 꼴). 운영 쓰기 없음.

사용자(2026-11-24): 「그냥 Codex에게 시키지말고 네가 처음부터 문항을 봐주면 안되나?」 → Codex scan2/scan3 대신
Claude 하위 에이전트가 원본부터 다시 본다. 결과는 <runId>/claude/edits-<n>.json, apply.py --source claude.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan import ROOT, WORK, payload  # noqa: E402

SPLIT = {'261123_01': 2, '261123_06': 2}

for rid in ['261123_01', '261123_02', '261123_03', '261123_05', '261123_06', '261123_07']:
    before = WORK / rid / 'before'
    doc = json.loads((before / 'document.json').read_text(encoding='utf-8'))
    mcq = json.loads((before / 'root_mcq.json').read_text(encoding='utf-8'))
    rows = payload(doc, mcq)
    n = SPLIT.get(rid, 1)
    size = -(-len(rows) // n)
    out = WORK / rid / 'claude'
    out.mkdir(exist_ok=True)
    material = ROOT / 'runs/_root-generation' / doc['revision'].removeprefix('auto-') / 'generation/material'
    for k in range(n):
        part = rows[k * size:(k + 1) * size]
        (out / f'questions-{k}.json').write_text(json.dumps(part, ensure_ascii=False, indent=1), encoding='utf-8')
        print(rid, k, len(part), material)
