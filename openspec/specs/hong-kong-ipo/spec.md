# Hong Kong IPO Specification

## Purpose

Define Hong Kong IPO observation data, disclosure refresh, and the evidence required before an IPO can be presented as executable.

## Requirements

### Requirement: IPO monitoring service

The service SHALL provide IPO list, upcoming, summary, detail, and disclosure-refresh endpoints under `/api/v1/hkipo/`.

#### Scenario: A user opens Hong Kong IPO monitoring

- GIVEN the user navigates to `/hkipo`
- WHEN the page loads
- THEN it requests normalized list and summary data
- AND it can request instrument detail using its code.

### Requirement: Disclosure refresh boundary

The IPO synchronization endpoint SHALL refresh the local disclosure manifest and invalidate relevant IPO cache entries; it SHALL not claim that every aggregate field is verified prospectus evidence.

#### Scenario: A refresh is requested

- GIVEN an authorized operational refresh is initiated
- WHEN the refresh completes
- THEN the response reports the number of synchronized items
- AND stale IPO cache entries are cleared.

### Requirement: Executability evidence

An IPO SHALL be marked executable only with traceable prospectus or official offering information, applicable subscription dates and channel, price or range, board lot, funding conditions, and later allocation/trading evidence as the state advances.

#### Scenario: An IPO only has aggregate listing data

- GIVEN an IPO record originates from an aggregate information table
- WHEN it lacks official offering and account-channel facts
- THEN it remains an observation
- AND it is not ranked as a verified low-risk or expected-profit trade.

### Requirement: Correct lot semantics

The system SHALL not infer Hong Kong IPO board-lot cost from an aggregate subscription limit or A-share-style maximum subscription field.

#### Scenario: An IPO contains `apply_limit`

- GIVEN an aggregate provider supplies an application limit
- WHEN a one-lot cost is needed
- THEN the system requires verified board-lot share count and offering price
- AND it does not multiply `apply_limit` by price as a substitute.

### Requirement: IPO state progression

The UI and domain model SHALL distinguish `观察`, `可执行`, `已提交/持有`, and `已确认退出条件`; each advance requires dated supporting evidence.

#### Scenario: Allocation results are pending

- GIVEN a user submitted an application but allocation results are unavailable
- WHEN the status is shown
- THEN it remains submitted rather than allocated
- AND the system does not present requested shares as tradable holdings.
