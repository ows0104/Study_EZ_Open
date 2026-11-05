"""Compatibility alias for shared professor information."""
import sys
from studyez_contracts.bank import professors as _implementation
sys.modules[__name__] = _implementation
