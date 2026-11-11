# StudyEZ agent entry

Read CLAUDE.md, then the relevant component guide and docs/map.md.
MANDATORY before touching any file for a new feature or fix (see "작업 시작 대원칙" in CLAUDE.md and
docs/development/collaboration.md): (1) create a new branch for this one feature from latest origin/master,
in its own worktree if other sessions are running; (2) `git pull` the dashboard (`dashboard` branch,
DASHBOARD.md in ../Study_EZ_dashboard); (3) check in-progress and planned work for overlapping files/areas
and stop to ask a human if any overlap; (4) add your task to "지금 하고 있는 작업" and push the dashboard.
Never merge the `dashboard` branch into master. Remove your row when the work is merged or abandoned.
Open PRs as drafts (`gh pr create --draft`), check locally, then `gh pr ready` once. Batch commits
before pushing to a ready PR: every push reruns CI against a monthly Actions-minute limit.
For every StudyEZ feature, fix or incident, follow docs/development/README.md:
intent.md → spec.md → plan.md → human-approved build → tests → reviewed release → important human approval → maintain.
Use scripts/development.py to create a change record and check revision-bound approval/test/release evidence.
Do not start implementation based only on a feedback message or automated incident record.
Current human authorization takes precedence and should not be requested again for the same approved scope.
Do not load work/, tmp/, generated data or historical instructions unless relevant to the task.
Content changes, lecture exceptions and archival actions require the applicable preserved policy in docs/policies/.
