"""Compatibility alias; canonical code is studyez_contracts.bank.choice_mode."""
import sys
from studyez_contracts.bank import choice_mode as _implementation

sys.modules[__name__] = _implementation
