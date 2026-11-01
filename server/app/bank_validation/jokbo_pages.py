"""Compatibility alias; canonical code is studyez_contracts.bank.jokbo_pages."""
import sys
from studyez_contracts.bank import jokbo_pages as _implementation

sys.modules[__name__] = _implementation
