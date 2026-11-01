"""Compatibility alias; canonical code is studyez_contracts.bank.validate."""
import sys
from studyez_contracts.bank import validate as _implementation

sys.modules[__name__] = _implementation
