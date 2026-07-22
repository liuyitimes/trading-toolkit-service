## 1. Storage and read path

- [x] 1.1 Add additive snapshot, observation, evidence, and refresh-job models.
- [x] 1.2 Implement snapshot repository and snapshot-only pending read payload.
- [x] 1.3 Add asynchronous deduplicated refresh with startup trigger; retry scheduling remains pending.

## 2. Data policy

- [ ] 2.1 Add field-group source reconciliation and review-required conflicts.
- [ ] 2.2 Add trading-calendar cadence, imminent-candidate cadence, retention cleanup, and manual-override audit.

## 3. Verification

- [ ] 3.1 Add deterministic persistence, stale-read, deduplication, backoff, and compatibility tests.
- [ ] 3.2 Verify cold reads do not invoke providers and startup refresh populates snapshots.
