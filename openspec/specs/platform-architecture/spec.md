# Platform Architecture Specification

## Purpose

Describe the boundaries and runtime responsibilities of the supported system.

## Requirements

### Requirement: Web and service separation

The Web application SHALL render decision-support workflows and consume versioned HTTP APIs. The Flask service SHALL own data acquisition, domain calculations, caching, persistent user data, and API response envelopes.

#### Scenario: A page loads market data

- GIVEN a user opens a supported Web route
- WHEN the route requires remote market data
- THEN the Web API client requests the Flask `/api/v1/` endpoint
- AND the service obtains or returns normalized domain data rather than exposing upstream response shapes.

### Requirement: Direct upstream integration

The service SHALL use the `DirectSource` facade, domain services, and `http_client` wrappers for upstream data access. New runtime dependencies on `akshare`, `efinance`, or `tushare` SHALL NOT be introduced as implicit fallback sources.

#### Scenario: A new Eastmoney request is added

- GIVEN a service needs Eastmoney data
- WHEN the upstream call is implemented
- THEN it uses the `em_get` wrapper
- AND inherits the configured timeout, retry, and serialized rate-limit behavior.

### Requirement: Normalized internal boundaries

Service domain modules SHALL emit English `snake_case` fields and SHALL not make clients interpret upstream Chinese field names.

#### Scenario: An upstream field is renamed

- GIVEN an upstream provider changes a raw field name
- WHEN the service adapts its parser
- THEN the normalized public field remains stable where possible
- AND any unavoidable contract change follows an OpenSpec API delta.

### Requirement: Persistence and cache tiers

The service SHALL support development-friendly local persistence/cache backends and production database/cache backends without changing public behavior. Cache state SHALL never be the sole evidence that a datum is fresh.

#### Scenario: Development runs without Redis

- GIVEN no `REDIS_URL` is configured
- WHEN the service starts locally
- THEN it uses its supported fakeredis or in-memory fallback
- AND maintains the documented cache and response semantics.
