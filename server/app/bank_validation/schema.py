"""Compatibility alias; canonical code is studyez_contracts.bank.schema."""
import sys
from studyez_contracts.bank import schema as _implementation

sys.modules[__name__] = _implementation
