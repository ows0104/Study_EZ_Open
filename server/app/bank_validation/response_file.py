"""Compatibility alias for shared file dispatch."""
import sys
from studyez_contracts.bank import response_file as _implementation
sys.modules[__name__] = _implementation
