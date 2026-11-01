"""Compatibility alias; canonical code is studyez_contracts.bank.quality."""
import sys
from studyez_contracts.bank import quality as _implementation

sys.modules[__name__] = _implementation
