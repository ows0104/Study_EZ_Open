"""Local per-call usage summary. Does not launch Codex or call a service."""
import argparse
import collections
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studyez_llm.execution import usage_root


def summary(root: Path):
    rows=[]
    for path in root.glob('*/*.json'):
        try:
            row=json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            continue
        if 'status' in row:
            rows.append(row)
    usage=collections.Counter()
    for row in rows:
        usage.update(row.get('usage') or {})
    return {'calls':len(rows),'statuses':dict(collections.Counter(r['status'] for r in rows)),
            'usage':dict(usage),'partialUsageUnknown':sum(bool(r.get('partialUsageUnknown')) for r in rows),
            'note':'Failed partial turns without final counters are unknown, not zero. Tokens do not map directly to weekly percentage.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=usage_root())
    args=parser.parse_args()
    print(json.dumps(summary(args.root),ensure_ascii=False,indent=2))
