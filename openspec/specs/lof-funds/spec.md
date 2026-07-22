# LOF Funds Specification

## Purpose

Define LOF listing, premium monitoring, opportunity analysis, and evidence boundaries.

## Requirements

### Requirement: LOF data service

The service SHALL provide list, opportunities, summary, share-history, and arbitrage-prediction endpoints for LOF funds.

#### Scenario: A user opens the LOF page

- GIVEN the user navigates to `/lof`
- WHEN the page loads
- THEN it can retrieve current list and summary data from `/api/v1/lof/`
- AND it can request instrument-specific share history and analysis when needed.

### Requirement: Premium data provenance

LOF premium and net-asset-value data SHALL use the normalized Eastmoney-backed implementation and retain status metadata. The service SHALL not represent zero-filled fallback fields as observed premium or NAV.

#### Scenario: An upstream LOF field is missing

- GIVEN the provider does not return a current valuation or premium field
- WHEN the endpoint responds
- THEN the field is unavailable or explicitly degraded
- AND it is not silently converted to a valid zero value.

### Requirement: Opportunity qualification

An LOF item SHALL not be described as executable solely because a premium exists. Executability requires current subscription/redemption terms, timing, capacity, and traceable issuer or manager evidence.

#### Scenario: A fund has a positive premium

- GIVEN a fund has a calculated market premium
- WHEN the list ranks or labels the item
- THEN it may be shown as an observation or analysis candidate
- AND it is not asserted to be directly arbitrageable without verified operational conditions.

### Requirement: Predictive analysis boundaries

Share-history and arbitrage-prediction outputs SHALL be identified as analysis rather than guaranteed outcome. Their sources, current-input time, and unavailable conditions SHALL remain observable.

#### Scenario: A prediction is requested without history

- GIVEN no usable share-history record exists for a fund
- WHEN the history endpoint is called
- THEN the service returns an appropriate not-found or unavailable response
- AND the client does not render an invented trend.

### Requirement: LOF desktop-table scanning and liquidity sorting

The LOF desktop tables SHALL use text-only metric headers and SHALL allow users to sort the `成交额` column by the normalized numeric `amountRaw` value in both the standard and arbitrage lists.

#### Scenario: A user scans an LOF table header

- GIVEN the standard or arbitrage LOF desktop table is visible
- WHEN the user views headers for 溢价率, 净溢价, 预期收益(万), and 成交额
- THEN the headers contain their textual labels without formula information icons.

#### Scenario: A user sorts by transaction amount

- GIVEN an LOF desktop table contains funds with different `amountRaw` values
- WHEN the user clicks the 成交额 header
- THEN the table sorts the visible rows by `amountRaw`
- AND repeated sorting can reverse the numeric order.
