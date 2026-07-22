# Closed-End Funds Specification

## Purpose

Define closed-end fund data display and prevent discount observations from being misrepresented as executable arbitrage.

## Requirements

### Requirement: Closed-end market monitoring

The service SHALL provide a list and summary under `/api/v1/closed-end/`, and the Web application SHALL expose the corresponding `/closed-end` workspace.

#### Scenario: A user visits the closed-end workspace

- GIVEN the user navigates to `/closed-end`
- WHEN the page requests data
- THEN it consumes the versioned closed-end list and summary APIs
- AND renders normalized price, NAV, discount, and source-status information when available.

### Requirement: Discount observation semantics

A discount between market price and disclosed NAV SHALL be displayed as an observation, not as an executable guaranteed return.

#### Scenario: Market price is below the last disclosed NAV

- GIVEN a fund trades below its reported NAV
- WHEN the UI calculates its discount
- THEN it may show the discount percentage
- AND it does not call the difference immediately redeemable profit.

### Requirement: Exit-event evidence

Annualized discount return or executable-arbitrage labels SHALL require a current, fund-level convergence or exit event with traceable evidence, event date, and NAV date.

#### Scenario: A fund lacks maturity or conversion evidence

- GIVEN a fund has no verified maturity, liquidation, open-end conversion, tender, or comparable exit event
- WHEN the system evaluates it
- THEN it remains an observation
- AND it does not calculate annualized discount return as an actionable result.

### Requirement: Temporal separation

The system SHALL preserve the difference between real-time exchange price and the date of the latest NAV disclosure.

#### Scenario: Price and NAV dates differ

- GIVEN intraday price and NAV originate on different dates
- WHEN the values are displayed
- THEN each time reference remains distinguishable
- AND the UI does not imply same-time comparability.

## Known limitation

The current client contains illustrative closed-end records and annualized-discount logic that depend on `maturity_date`; until fund-level exit evidence is available, this behavior is not an executable-strategy specification.
