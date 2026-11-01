"""Compatibility alias; canonical code is studyez_contracts.bank.publication."""
import sys
from studyez_contracts.bank import publication as _implementation

sys.modules[__name__] = _implementation
