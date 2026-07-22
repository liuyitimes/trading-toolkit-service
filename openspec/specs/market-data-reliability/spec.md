# Market Data Reliability Specification

## Purpose

Define truthfulness, caching, source attribution, and failure behavior for external financial data.

## Requirements

### Requirement: Explicit data freshness state

Endpoints using stale-cache fallback SHALL distinguish `fresh`, `stale`, and `unavailable` data states.

#### Scenario: An upstream request fails with a cached value available

- GIVEN a forced refresh cannot reach its upstream
- WHEN a previous successful cache value exists
- THEN the service returns that value with `data_status: "stale"`
- AND the Web experience identifies it as delayed rather than real-time.

#### Scenario: An upstream request fails without a cached value

- GIVEN a request cannot reach its upstream
- AND no prior successful cache value exists
- WHEN the endpoint responds
- THEN it returns an unavailable or structured source-error state
- AND it does not manufacture a market value.

### Requirement: Upstream access discipline

All upstream HTTP calls SHALL use the provider-specific HTTP wrappers. Eastmoney access SHALL preserve serialized rate limiting, while Sina, Tonghuashun, and Legu calls SHALL use their respective wrappers.

#### Scenario: A provider client is extended

- GIVEN a new request to a known provider is required
- WHEN it is added to a domain service
- THEN it uses the matching wrapper rather than directly calling `requests`.

### Requirement: Source and timestamp visibility

Data intended for user decision support SHALL retain source and update-time metadata through the service envelope. Web views SHOULD make stale or unavailable states observable at the point of use.

#### Scenario: A cached list is rendered

- GIVEN a list endpoint returns source metadata
- WHEN the Web view renders its result
- THEN the data is not described as verified real-time data if metadata marks it stale.

### Requirement: No deceptive mock fallback

Mock or inferred values SHALL be explicitly identified in development/testing and SHALL NOT be used to disguise unavailable market data in supported production behavior.

#### Scenario: A provider has no response

- GIVEN live retrieval fails
- WHEN no valid stale value is available
- THEN the endpoint reports the failure state
- AND does not substitute randomized or unlabelled mock values.
