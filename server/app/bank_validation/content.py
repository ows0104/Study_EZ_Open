"""Compatibility alias; canonical code is studyez_contracts.bank.content."""
import sys
from studyez_contracts.bank import content as _implementation

sys.modules[__name__] = _implementation
