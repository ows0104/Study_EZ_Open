# Merge review

Parents: session work `cf03cbc08ddaba2ec1b08c50d579d023573a036f` and fetched master
`0fcdce3de257ca6147e49fd4d045c654fceb7a11`.

The remote includes a historical merge with removals of functionality already present in the session branch.
The resolution preserves that functionality and its regression tests rather than accepting those removals.
The intermediate merged files and both parent diffs were backed up and hash-checked locally before
resolving those groups. No source PDF, management JSON, or image package was selected for Git.

Incoming changes were checked as follows:

- `0fcdce3d`: all 11 non-document files outside compact conversion match remote master exactly.
  Compact conversion retains the remote repeated-cloze/file parsing behavior, uses the shared contract
  import, and additionally handles blank section separators with strict ID checks and regression tests.
- `b1d50256`: nine non-document files match exactly. The bank router is a compatibility entry point;
  AST comparison of remote functions against the owner modules confirms that retention behavior is present.
  The bank test mocks continue to target those owner modules.
- `91fb6b0c`: all four changed code/test files match remote master exactly, preserving administrator usage data.

The modular bank function differences retain stricter edit concurrency/publication checks and matching
presentation behavior. The runner difference retains pin-aware slice cache invalidation and hidden Windows
subprocess handling. Manual/file response precedence, authored learning order, excluded questions, unknown
matching responses, study histories, and personal source pins remain intact.

Final changes relative to the session tip are limited to Windows change-record I/O retry, corrected
regression fixtures, explicit UTF-8 reads, the incoming cloze regression test, current extension/deployment
documentation, and this development record. Validation results are revision-bound in state.json.
