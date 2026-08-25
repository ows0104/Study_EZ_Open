# Prompt architecture

The quiz pipelines build their runtime instructions from small prompt modules.
This keeps broadly useful quiz-writing rules separate from source-specific and
domain-specific behavior.

## Composition order

1. `pdf2anki/prompts/core/`: rules that should hold for almost any quiz
2. `pdf2anki/prompts/profiles/`: the learning purpose, such as exam review or
   pre-lecture preparation
3. `pdf2anki/prompts/adapters/`: rules enabled only when a matching input is
   present, such as a lecture PDF, annotations, or a past exam
4. `pdf2anki/prompts/domains/`: terminology or conventions for one domain; the
   runtime default is `medical_ko`, while `generic` remains selectable
5. A short stage prompt, such as planning, card generation, or repair
6. The generated input and output contract

`pdf2anki/prompting.py` owns the shared composition order. The main and
pre-lecture pipelines select different profiles but use the same core.

## Where a new rule belongs

- Put it in `core/` only if it improves quizzes across unrelated subjects and
  input types.
- Put it in a profile only if it follows from that learning purpose.
- Put it in an adapter only if the relevant source or metadata can be detected
  at runtime.
- Put it in a domain module only if it depends on that domain, and keep the
  generic path free of it.
- Keep a one-off failure as a regression test or evaluation example rather than
  copying its story into the runtime prompt.

Prefer fixing validators, schemas, or deterministic selection logic when the
requirement can be checked mechanically. Prompts should describe judgment that
the model actually needs to make.

## Current selections

- Main cards: `exam_review` profile, `medical_ko` domain by default
- Pre-lecture cards: `prelecture` profile, `medical_ko` domain by default
- Past-exam adapter: enabled only when a past-exam file is supplied
- Medical past-exam repair: enabled only for Main cards when `medical_ko` and a
  past-exam source are both active; answer review uses the same domain/source gate
- `generic`: available with `--domain generic`
