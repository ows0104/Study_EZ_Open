# Authoring assets

bank/ owns bankPrompt.md, lectureScopes.json and delivery instructions.
Web and local generation consume the same source. Build prepares web/public/bank-prompt.json.
Change content only for an authorized authoring-policy change; preserve versions during structural moves.
Run tests/quizbank/test_generate.py, test_runtime.py and web/tests/bank-prompt-current.test.cjs.
