## ADDED Requirements

### Requirement: LOF market-direction and net-subscription overview

The LOF overview SHALL show the highest-premium market direction, prior-trading-day net subscription capital estimate, and estimated net-subscription participant count only when sourced from dated, verified LOF share-change records.

#### Scenario: Verified prior-day share records are available

- GIVEN the service has a dated, verified LOF share-change record for the latest completed trading day
- WHEN it produces the LOF overview
- THEN it reports a documented market-direction label
- AND calculates net subscription capital from positive net-share change and matching NAV
- AND estimates participants only for funds with a verified per-account subscription limit.

#### Scenario: Share records are unavailable or unverified

- GIVEN the service cannot obtain verified prior-day LOF share-change records
- WHEN it produces the LOF overview
- THEN it returns explicit unavailable fields and source status
- AND the Web application renders `暂缺` rather than mock or turnover-derived values.

#### Scenario: A fund has no verified subscription limit

- GIVEN a fund has a verified positive net-share change but no verified per-account subscription limit
- WHEN the participant estimate is calculated
- THEN its capital may contribute to the net-subscription capital total
- AND it does not contribute to the participant estimate.

### Requirement: Limit-type-aware participation equivalents

The service SHALL derive participation lower bounds only from official fund announcements that pair a dated positive net-share-change record with a current subscription limit. It SHALL preserve whether the announcement applies per fund account or per investor, without claiming natural-person identity.

#### Scenario: An announcement limits each account

- GIVEN an official announcement states a daily maximum subscription amount per account
- AND a compatible positive net-share increase is available for that day
- WHEN the service estimates participation
- THEN it calculates an account-count lower bound using the per-account cap
- AND it labels the result as `按单账户限额折算的账户数下限`, not as people.

#### Scenario: An announcement limits each investor or person

- GIVEN an official announcement states a daily maximum subscription amount per investor or person
- AND a compatible positive net-share increase is available for that day
- WHEN the service estimates participation
- THEN it calculates an investor-limit lower bound using the per-investor cap
- AND it does not label the result as verified unique people.

#### Scenario: Results are aggregated across funds or dates

- GIVEN multiple fund-day estimates are available
- WHEN the service produces a market total
- THEN it sums them as `累计等效参与次数`
- AND it does not claim cross-fund or cross-day deduplication of accounts, investors, or natural persons.

### Requirement: Market-direction classification transparency

The highest-premium market direction SHALL be derived through a documented fund taxonomy, with the underlying funds and classification rule available for inspection.

#### Scenario: A fund name does not match a known direction

- GIVEN a positive-premium fund cannot be classified by the documented taxonomy
- WHEN it is considered for the overview
- THEN the summary counts it as `其他/未识别` coverage
- AND it is excluded from the named-theme ranking rather than labelled as a market theme without evidence.
