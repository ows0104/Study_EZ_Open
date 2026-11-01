"""Compatibility alias; canonical code is studyez_contracts.bank.pool_checks."""
import sys
from studyez_contracts.bank import pool_checks as _implementation

sys.modules[__name__] = _implementation
