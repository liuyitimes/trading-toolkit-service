# Trading Toolkit Service OpenSpec

`openspec/specs/` is the versioned source of truth for behavior owned by the Flask service. It travels with the `trading-toolkit-service` Git repository so a clone on any device includes the current baseline and active changes.

## Scope

- Versioned HTTP endpoints, response envelopes, data collection, normalization, cache, persistence, and server-side calculations.
- Data provenance, degraded-data behavior, operational configuration, and the Python backtest package.
- Service-side requirements for a shared API contract.

The independently versioned `trading-toolkit-web` repository owns Vue routes, views, client-side calculations, and browser persistence. A feature that crosses these boundaries SHALL use the same change name in both repositories; each change artifact describes only its repository's work and identifies the companion change.

## Workflow

1. Read the relevant baseline specification under `openspec/specs/`.
2. Create or update `openspec/changes/<change-name>/` before implementation.
3. Complete proposal, delta specifications, design, and tasks.
4. Verify the implementation and run `openspec validate <change-name> --json`.
5. Archive an accepted change in this repository to merge its deltas into this Service baseline.
