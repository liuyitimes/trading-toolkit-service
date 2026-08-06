## 1. Storage and read path

- [x] 1.1 Add additive snapshot, observation, evidence, and refresh-job models.
- [x] 1.2 Implement snapshot repository and snapshot-only pending read payload.
- [x] 1.3 Add asynchronous deduplicated refresh with startup trigger and exponential retry scheduling.

## 2. Data policy

- [x] 2.1 Add field-group source reconciliation and review-required conflicts.
- [x] 2.2 Add trading-calendar cadence, imminent-candidate cadence, retention cleanup, and manual-override audit.

## 3. Verification

- [x] 3.1 Add deterministic source-priority, stale-read, cadence, and compatibility tests.
- [x] 3.2 Verify the deployed snapshot API returns immediately and the startup refresh populates persisted candidates.
