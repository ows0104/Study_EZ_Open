"""Compatibility alias; canonical code is studyez_contracts.bank.slide_focus."""
import sys
from studyez_contracts.bank import slide_focus as _implementation

sys.modules[__name__] = _implementation
