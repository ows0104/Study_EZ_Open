"""Compatibility alias; canonical code is studyez_contracts.bank.evidence_resolution."""
import sys
from studyez_contracts.bank import evidence_resolution as _implementation

sys.modules[__name__] = _implementation
