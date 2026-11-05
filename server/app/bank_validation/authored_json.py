"""Compatibility alias for the shared authored JSON contract."""
import sys
from studyez_contracts.bank import authored_json as _implementation
sys.modules[__name__] = _implementation
