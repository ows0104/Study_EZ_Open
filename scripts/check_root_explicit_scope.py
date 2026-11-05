"""Explicit root claim/runner scope checks using isolated nonmedical fixtures."""
import sys
from check_connection_generation import pytest,server

name=sys.argv[1]
if name=='contracts':pytest('tests/contracts')
elif name=='runner':pytest('tests/runner')
elif name=='server':
    for pattern in ('root_generation','root_web_generation','root_one_click','root_job_claim','job_board','route_contract'):
        server(pattern)
else:raise SystemExit('Unknown check: '+name)
