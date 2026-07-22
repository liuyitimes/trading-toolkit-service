## Context

LOF rows currently provide current price, latest unit NAV, premium, same-session turnover and volume, verified execution-rule evidence, and a bounded five-session turnover lookup. The existing detail is a 640px dialog in `Lof.vue`; it derives a fixed-cost net premium in the client and invokes `/arbitrage-predict`. That prediction can fall back to mock share history, while the in-progress `lof-market-overview-signals` change has established that this fallback is not decision-grade.

The redesigned view must serve a researcher assessing an arbitrage candidate over the settlement period. It needs historical observations and provenance that are not available in the present list response.

## Goals / Non-Goals

**Goals:**

- Provide one deep-linkable LOF detail workspace in the Web application.
- Put decision-critical data in this order: premium, persistence, execution capacity, fund exposure, then volatility risk.
- Persist and expose observed history with date and source metadata.
- Preserve clear unavailable states rather than synthesize a complete-looking signal.

**Non-Goals:**

- Brokerage-account synchronization, order placement, or a claim about a user's actual holdings.
- A combined buy/sell score or a guaranteed-return label.
- Reusing `lof_arbitrage` mock history for any detail metric.
- Changes to `trading-toolkit-mp`.

## Decisions

### Use a dedicated detail API

The service will provide `GET /api/v1/lof/:code/detail` for the Web detail route. It separates history and holdings from list responses, so list refreshes stay bounded and the detail response retains independent freshness and provenance.

The detail API will return one normalized envelope with these groups:

| Group        | Required content                                                                  |
| ------------ | --------------------------------------------------------------------------------- |
| `instrument` | code, name, exchange, quote time, NAV date, validity state                        |
| `execution`  | subscription/custody/sale-path evidence, cap, and evidence freshness              |
| `premium`    | current gross premium, cost-assumption net premium, and observed history summary  |
| `liquidity`  | current turnover/volume plus dated rolling turnover observations                  |
| `holdings`   | dated fund portfolio holdings and concentration, or an explicit unavailable state |
| `volatility` | dated price, NAV, and premium variation measures with their windows               |
| `provenance` | source URL or identifier, observed-at, retrieved-at, and freshness for each group |

The alternative of extending `/lof/list` is rejected because histories and holdings would make every list request expensive and blur list-vs-detail freshness.

### Return decision-oriented response groups

The detail response groups evidence in this order: instrument identity and freshness, execution-path state, premium persistence, liquidity, fund exposure, settlement-window risk, and provenance. Each group carries its own availability and freshness fields so the Web client can render unavailable data without manufacturing a fallback.

### Persist observed data server-side

The service will write timestamped observations after a valid LOF quote is fetched. A detail request reads this store for premium persistence and liquidity history; it does not manufacture missing periods. Portfolio holdings are stored separately with the manager or official-disclosure date and source identifier.

Client-side history accumulation is rejected because it loses continuity on refresh, cannot support provenance, and is unavailable to a first-time viewer. An unverified public-source fallback is rejected by the repository data-reliability rules.

### Separate holdings from shares and modeled capital flows

`holdings` means the fund's disclosed investment portfolio, not user holdings and not total LOF units. Total units or net subscription changes, if later available from a verified source, belong in a separately named fund-share-supply analysis group. The existing prediction endpoint remains analysis-only; mock-source responses are not consumed by the redesigned detail view.

### Risk measures remain decomposed

The first implementation will show components rather than a black-box composite score:

- premium persistence: positive-session count, min/max/range, and current deviation from observed range;
- liquidity: current turnover/volume and rolling turnover comparison;
- market/NAV risk: price return range, premium range, and NAV change over stated windows;
- exposure risk: disclosure-date concentration and top holdings.

This is preferred over a single score because each input has different freshness and evidence quality.

## Risks / Trade-offs

- [A verified holdings source may be quarterly and stale] -> show the disclosure date prominently and mark it unavailable when no source exists; never imply intraday holdings.
- [Observed history begins only after deployment] -> render an insufficient-history state until documented windows are complete.
- [The current list has a fixed client-side fee assumption] -> label it as an editable/documented assumption; do not represent it as an account-specific cost.
- [A detail endpoint adds calls and storage] -> defer history and holdings fetches until a user opens the route, cache by source freshness, and keep the list endpoint lightweight.
- [The active market-overview change is incomplete] -> keep its net-subscription fields out of this detail contract until its verified source decision is complete.

## Migration Plan

1. Add the detail contract and storage without changing list semantics.
2. Backfill only verified observations and disclosures; show unavailable states for all other instruments.
3. Add the `/lof/:code` route and migrate list-row navigation from the dialog.
4. Remove the old dialog after parity testing and preserve the list route as the rollback path.
5. Roll back by disabling detail navigation and returning users to the existing list; retain stored observations for later recovery.

## Open Questions

1. Does “持仓” mean fund portfolio exposure, the user's own position, or both? This design assumes fund portfolio exposure because no brokerage-position source exists.
2. Which official or manager source will provide dated portfolio holdings, and what maximum disclosure age is acceptable?
3. Which observed windows are required for premium persistence and volatility: 5/20 sessions, calendar days, or both?
4. Should the net-premium assumption be user-configurable, and which subscription/commission schedule is authoritative for the first release?
