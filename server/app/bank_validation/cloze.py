"""Compatibility alias; canonical code is studyez_contracts.bank.cloze."""
import sys
from studyez_contracts.bank import cloze as _implementation

sys.modules[__name__] = _implementation
