# LOF Market Overview Signals

## Why

The current LOF overview shows broad market counts and exchange-based average premium. The desired decision view instead needs the highest-premium market direction, prior-trading-day subscription-share-derived capital scale, and an estimated participant count.

## Intended outcome

Replace the four existing overview cards with:

1. Highest-premium market direction.
2. Prior-trading-day net subscription capital estimate.
3. Prior-trading-day estimated subscription participants.

## Evidence and constraint

The existing share-history implementation requests Eastmoney report `RPT_FUND_LOF_SHARE_CHANGE`. On 2026-07-14 the upstream returned `9501: 报表配置不存在`; the existing fallback generates mock history. Mock history cannot support a decision metric and SHALL NOT be used by this overview.

Daily share change, where available, represents net subscriptions after redemptions. It does not prove gross applications or exact individual count. The UI must therefore use the terms `净申购资金（估）` and `净申购账户（估）`, identify the source date, and show unavailable state when no verified source is available.

Where a fund announcement records a positive share increase and a current subscription cap, the system may calculate a lower-bound participation proxy. It must distinguish a `per-account` cap from a `per-investor` cap. Neither establishes natural-person identity. Aggregating across funds or dates cannot deduplicate entities, so the all-market value is an `累计等效参与次数`, never a unique participant total.

## Scope

- Add a verified daily LOF net-subscription source or an explicitly maintained source feed.
- Derive a transparent market-direction label from a documented LOF taxonomy.
- Expose the three decision signals, source dates, and unavailable states through the LOF summary contract.

## Repository scope

This Service change owns the verified data source, aggregation, provenance, unavailable-state metadata, and LOF summary response. The matching `lof-market-overview-signals` change in `trading-toolkit-web` owns the overview cards and their presentation.

## Out of scope

- Mini-program behavior.
- Displaying mock, inferred-from-turnover, or unverified values as fund subscriptions.
- Claiming gross application count, allocation count, or guaranteed arbitrage capacity.

## Rollback

Restore the previous overview cards and remove the new summary fields if the verified source is withdrawn or the calculation proves incorrect.
