"""Verify saved manual CUA observations and read-only fixture state; no browser automation."""
from pathlib import Path
import json,sys
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[3]
proof=json.loads((ROOT/'runs/_main-quiz/261106/browser-proof.json').read_text(encoding='utf-8'))
assert proof['productionConnected'] is False and proof['url']=='http://127.0.0.1:5198/bank/map-point-e2e/cns-infection'
assert len(proof['observed'])==15
assert proof['mobile']['documentWidth']<=proof['mobile']['width']==390
assert 'Main Quiz' in proof['dom'] and '급성 세균성' in proof['dom'] and '[ 4 ]' in proof['dom']
for file in proof['screenshots']:assert Path(file).read_bytes().startswith((b'\x89PNG',b'\xff\xd8'))
def read(path):
 with urlopen('http://127.0.0.1:8037'+path,timeout=10) as response:return json.load(response)
entry=read('/api/main-quiz/lectures/map-point-e2e/cns-infection/entry')
assert entry['mode']=='structured' and entry['overview']['summary']['total']==3
v=read('/api/root-learning/sessions/'+entry['overview']['sessionId'])
assert v['position']==4 and v['count']==7 and v['task']['answer'] is None
assert read('/api/main-quiz/lectures/test/legacy/entry')=={'mode':'legacy'}
legacy=read('/api/lectures/test/legacy/bank')
assert legacy['summary']['usable'] and legacy['session']['status']=='active'
print('PASS: 15 manually observed CUA cases, desktop screenshot and observed mobile layout, final canonical structured task, canonical legacy active session; production writes 0')
