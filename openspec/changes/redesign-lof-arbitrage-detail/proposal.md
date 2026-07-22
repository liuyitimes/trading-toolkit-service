## Why

The current LOF detail is a 640px dialog that mixes quote fields, a fixed-fee return estimate, generic advice, and a capital-flow prediction. It does not organize evidence around the decisions an arbitrage researcher needs to make: whether the premium survives, whether the position can be entered and exited, and what portfolio or volatility risk is carried during the settlement window.

## What Changes

- Replace the LOF detail dialog with a deep-linkable arbitrage-research detail view organized around premium, premium persistence, liquidity, fund holdings exposure, and volatility risk.
- Separate observed, verified execution data from analytical estimates and unavailable data; mock share-history data MUST NOT be rendered as a position, capital-flow, or risk signal.
- Add a documented detail-data contract for historical premium/liquidity/volatility observations and disclosed fund holdings, including source and as-of dates.
- Preserve the existing list and market-overview behavior. The in-progress `lof-market-overview-signals` change remains independent and is not a prerequisite for this detail view.

## Repository scope

This Service change owns the LOF detail API, persisted observations, holdings-disclosure storage, data provenance, and unavailable-state representation. The matching `redesign-lof-arbitrage-detail` change in `trading-toolkit-web` owns route navigation, detail layout, charts, and responsive verification.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `lof-funds`: Add a decision-oriented LOF arbitrage detail requirement, including evidence, unavailable-state, and risk-disclosure rules.

## Impact

- Affected supported module: `trading-toolkit-service` (detail API and persisted observation/holdings data).
- Public API: a versioned LOF detail endpoint and its evidence metadata will be added; existing list, summary, share-history, and prediction endpoints remain compatible.
- Data sources/cache: persisted premium and liquidity observations plus dated disclosed holdings are required; data retention and refresh policy must be documented.
- The unmaintained `trading-toolkit-mp` application is explicitly out of scope.
- Rollback: retain the existing LOF list; remove the new route and detail endpoint if the evidence contract cannot be maintained, without representing unavailable history as observed data.
