# Persist Placement Snapshots

## Why

`GET /api/v1/convertible/pending` synchronously collects slow providers on a cold cache miss. This can exceed the Web timeout and hide imminent candidates.

## Scope

Persist current Placement Snapshots and append-only observations; refresh them asynchronously; return persisted data immediately with freshness and provenance metadata. This is the service half of the same-named Web change.

## Rollback

The new tables are additive. The endpoint maintains the existing top-level response envelope and can fall back to an empty snapshot payload while the previous synchronous code is restored in an emergency.
