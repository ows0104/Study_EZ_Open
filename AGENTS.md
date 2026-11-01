# StudyEZ agent entry

Read CLAUDE.md, then the relevant component guide and docs/map.md.
For every StudyEZ feature, fix or incident, follow docs/development/README.md:
intent.md → spec.md → plan.md → human-approved build → tests → reviewed release → important human approval → maintain.
Use scripts/development.py to create a change record and check revision-bound approval/test/release evidence.
Do not start implementation based only on a feedback message or automated incident record.
Current human authorization takes precedence and should not be requested again for the same approved scope.
Do not load work/, tmp/, generated data or historical instructions unless relevant to the task.
Content changes, lecture exceptions and archival actions require the applicable preserved policy in docs/policies/.
