"""Compatibility alias; canonical code is studyez_contracts.bank.priorities."""
import sys
from studyez_contracts.bank import priorities as _implementation

sys.modules[__name__] = _implementation
