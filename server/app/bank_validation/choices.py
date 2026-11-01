"""Compatibility alias; canonical code is studyez_contracts.bank.choices."""
import sys
from studyez_contracts.bank import choices as _implementation

sys.modules[__name__] = _implementation
