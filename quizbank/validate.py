"""Generation uses the same structural checks as server-side card edits."""
from studyez_contracts.bank.validate import (
    EXTERNAL as EXTERNAL, validate_bank as validate_bank, validate_dropping as validate_dropping,
)
