"""Compatibility alias; canonical code is studyez_contracts.bank.coverage."""
import sys
from studyez_contracts.bank import coverage as _implementation

sys.modules[__name__] = _implementation
