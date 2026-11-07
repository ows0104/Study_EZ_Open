"""Check the isolated prompt copy against its pinned format; no model calls."""
import json
import re
import subprocess
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]


def old(path):
    return subprocess.run(['git', 'show', '59b6b405:' + path], cwd=ROOT,
                          check=True, capture_output=True).stdout.decode('utf-8')


source = old('content/prompts/learning-links/map-extract.md')
copy = (ROOT / 'content/prompts/learning-links/map-extract-reference.md').read_text(encoding='utf-8')
schema = json.loads(old('content/prompts/learning-links/map-output.schema.json'))
Draft202012Validator.check_schema(schema)
def sample(text):
    blocks = re.findall(r'```json\s*([\s\S]*?)```', text)
    assert len(blocks) == 1
    return json.loads(blocks[0])
assert sample(copy) == sample(source)
Draft202012Validator(schema).validate(sample(copy))
assert len(copy.split('## 출력')[0].splitlines()) == len(source.split('## 출력')[0].splitlines())
assert 'concept-map.json' in copy and 'UTF-8' in copy
assert all(word not in copy for word in ('문항', '누락 판정', '회상 목표'))
print(json.dumps({'schema_compatible': True, 'example_unchanged': True,
                  'same_instruction_line_count': True, 'model_calls': 0}))
