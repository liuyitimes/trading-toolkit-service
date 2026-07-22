# Snapshot Persistence Design

SQLite receives additive `placement_candidate`, `placement_snapshot`, `placement_observation`, `placement_source_evidence`, and `placement_refresh_job` tables. The first delivery stores the normalized pending list as snapshot JSON while preserving its candidate identifiers, and records a refresh job lifecycle. This provides immediate reads without a destructive migration of the existing dirty database.

The endpoint returns `{ items, meta }` inside the existing response envelope. Existing Web code can already normalize a list or an object with `data`; its companion change adds metadata presentation. Startup and stale reads schedule a daemon job. The job calls the existing source factory, persists the accepted result atomically, and applies retry backoff after failures.

Source-field reconciliation, announcement extraction, source evidence, retention cleanup, and trading-calendar scheduling are staged follow-up tasks. They are explicitly represented in the task list so the initial latency fix does not falsely claim their completion.
