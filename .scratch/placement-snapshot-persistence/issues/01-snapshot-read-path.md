# 01 - Snapshot Read Path

Type: feature
Status: resolved
Labels: feature, backend, api-contract

Create additive persistence models and replace synchronous pending reads with a snapshot-only payload plus asynchronous refresh.

## Answer

The pending endpoint now reads additive SQLite snapshots only and schedules provider collection in a daemon refresh job. It preserves the top-level response envelope and returns snapshot metadata with the items.
