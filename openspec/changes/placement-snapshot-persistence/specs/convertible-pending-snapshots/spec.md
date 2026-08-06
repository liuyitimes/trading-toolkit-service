## ADDED Requirements

### Requirement: Snapshot-only pending reads

The service SHALL serve `GET /api/v1/convertible/pending` from locally persisted placement snapshots and SHALL NOT wait for external provider I/O. The response SHALL retain the existing API envelope and expose items plus `data_as_of`, `freshness_state`, `stale_reason`, `verification_state`, and `review_required` in its data payload.

#### Scenario: A cold upstream provider is slow

- GIVEN there is a persisted placement snapshot
- WHEN an external provider is slow or unavailable
- THEN the API returns the persisted items immediately
- AND THEN it identifies the snapshot as stale when appropriate.

#### Scenario: A candidate registers today or tomorrow

- GIVEN an imminent candidate exists in the latest snapshot
- WHEN market fields are stale
- THEN the API retains the candidate through its registration date.

### Requirement: Asynchronous placement refresh

The service SHALL deduplicate equivalent Placement Refresh Jobs. A stale read SHALL enqueue at most one matching job and a forced refresh SHALL create or observe a job without waiting for provider I/O. Jobs SHALL retry with exponential backoff.

#### Scenario: Two stale reads arrive together

- GIVEN no equivalent job is active
- WHEN two stale reads arrive concurrently
- THEN the service schedules one refresh job
- AND THEN both reads return without provider I/O.

### Requirement: Snapshot history and source precedence

The service SHALL retain current snapshots through 30 days after registration and append source-aware observations for three years. Lower-priority source data SHALL NOT overwrite verified higher-priority issuer terms; equal-priority conflicts SHALL retain both observations and set `review_required`.

#### Scenario: A lower-priority source disagrees with verified issuer terms

- GIVEN a verified official issuer-term field exists
- WHEN a lower-priority provider supplies a different value
- THEN the verified value remains current
- AND THEN the incoming value is retained as an observation.
