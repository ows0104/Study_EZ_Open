# Shared contracts

bank/ is canonical. Only Python standard library and sibling pure modules may be imported.
Server legacy paths re-export these exact modules for compatibility. Do not add DB, FastAPI or model calls.
Schema/policy semantics are unchanged by relocation. Contract changes require producer and consumer checks.
Run tests/contracts, relevant tests/quizbank, and server bank/route/retention checks.
Independent server environment: install server/requirements.txt from server/ (includes this editable package).
Cloud build context must be created with server/prepare-build.ps1; never deploy a bare server/ directory.
