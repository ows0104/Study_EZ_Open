"""Frozen-identity checks use synthetic sources and isolated local databases."""
import sys
from check_connection_generation import pytest,server,main

name=sys.argv[1]
if name=='contracts':pytest('tests/contracts')
elif name=='server':
    for pattern in ('root_generation','root_web_generation','root_one_click','root_job_claim','root_preservation','route_contract'):
        server(pattern)
elif name=='web':main('web')
else:raise SystemExit('Unknown check: '+name)
