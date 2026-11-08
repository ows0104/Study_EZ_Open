# Shared contracts

bank/ is canonical. Only Python standard library and sibling pure modules may be imported.
bank/quality.py measures answer disclosure, recall load, structural answer cues and format spread.
Only disclosure of every answer unit is an error; every measure added 2026-11-08 is a warning, so it
never drops a question. Its lines are the p97 tail of the live Quiz Bank, not authoring rules — change
the constants, not the code. A basic answer has one scoring unit (live Quiz Bank: 99.5%); more than one is
warned as a wrong format. roots/generation_v2.quality_reasons turns these warnings into question_fix repair
reasons inside the existing 3-round budget. Tests: tests/quizbank/test_answer_quality.py.
bank/importance.py (importance-basis/1) scores exam-point-extract/3 point evidence into tier and bank 3.3
importance (5/4/3/2) and review target axes; roots/generation_v2.project_importance applies it at assembly
and validate_result recomputes it. Weights are administrator decisions (docs/changes/2026-11-08-importance-basis);
change them only with a new decision. Tests: tests/contracts/test_importance_basis.py, tests/quizbank/test_importance_projection.py.
learning_links/ owns the separate v1 connection-review contract and question fingerprints.
It does not mutate BANK, certify medical judgments, or create learner state. Consumers call
validate_review with hashes calculated from the actual inputs. Tests: tests/contracts/test_learning_links.py.
Server legacy paths re-export these exact modules for compatibility. Do not add DB, FastAPI or model calls.
Schema/policy semantics are unchanged by relocation. Contract changes require producer and consumer checks.
Run tests/contracts, relevant tests/quizbank, and server bank/route/retention checks.
Independent server environment: install server/requirements.txt from server/ (includes this editable package).
Cloud build context must be created with server/prepare-build.ps1; never deploy a bare server/ directory.

roots/ wraps learning_links with adopted targets, explicit target prerequisites, whole-direction tasks and reviewed identity links. It never copies the goal/direction/evidence schema or certifies medical correctness. Tests: tests/contracts/test_roots.py.

roots/generation_v2.py defines the opt-in source-assessment/2 generation contract and learning-links/2 extension. Legacy /1 remains readable. Component answer evidence, current source/importance checks, immutable PNG bytes, and combined question/target prerequisites gate preparation. Semantic truth is still reviewed by content models. Tests: test_generation_v2.py and test_generation_pipeline_v2.py.
