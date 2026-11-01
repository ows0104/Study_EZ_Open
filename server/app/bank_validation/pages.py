"""Compatibility alias; canonical code is studyez_contracts.bank.pages."""
import sys
from studyez_contracts.bank import pages as _implementation

sys.modules[__name__] = _implementation
