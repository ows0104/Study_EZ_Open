"""Source-assessment cause-fix checks, isolated synthetic inputs only."""
import sys
from check_connection_generation import pytest,server
name=sys.argv[1]
if name=='contracts':pytest('tests/contracts')
elif name=='generation':pytest('tests/quizbank/test_connection_generate.py','tests/quizbank/test_generate.py','tests/quizbank/test_runtime.py')
elif name=='runner':pytest('tests/runner/test_connection_generation.py','tests/runner/test_root_session_resume.py')
elif name=='server':
    for pattern in ('root_source_assessment','root_generation','root_web_generation','root_one_click','root_preservation','route_contract'):
        server(pattern)
else:raise SystemExit('Unknown check: '+name)
