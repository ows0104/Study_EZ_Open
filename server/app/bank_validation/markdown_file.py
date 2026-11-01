"""Compatibility alias; canonical code is studyez_contracts.bank.markdown_file."""
import sys
from studyez_contracts.bank import markdown_file as _implementation

sys.modules[__name__] = _implementation
