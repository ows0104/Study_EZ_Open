"""Compatibility alias; canonical code is studyez_contracts.bank.importance."""
import sys
from studyez_contracts.bank import importance as _implementation

sys.modules[__name__] = _implementation
