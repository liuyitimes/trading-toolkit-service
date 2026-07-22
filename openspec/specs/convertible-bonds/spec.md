# Convertible Bonds Specification

## Purpose

Define the current convertible-bond monitoring, signals, and original-shareholder placement behavior.

## Requirements

### Requirement: Convertible monitoring endpoints

The service SHALL provide list, signals, market-temperature, detail, and pending-placement data under `/api/v1/convertible/`.

#### Scenario: A user opens the convertible workspace

- GIVEN the user navigates to `/convertible`
- WHEN the view loads its data
- THEN it obtains normalized list, signal, and pending-placement data from the versioned API
- AND it can request detail for an individual bond code.

### Requirement: Placement field semantics

For pending placement, `per_share_allocation` SHALL mean per-share convertible face-value allocation, `shares_for_10_lots` SHALL mean the shares required for 1,000 yuan face value, and `cash_ratio` SHALL mean face value obtainable per 100 yuan of stock market value.

#### Scenario: Cash ratio is rendered

- GIVEN `per_share_allocation` and `stock_price` are available
- WHEN the service computes the placement metric
- THEN `cash_ratio = per_share_allocation / stock_price * 100`
- AND it does not use `stock_cash_ratio` as a substitute.

### Requirement: Placement cost and integer-lot display

The Web placement view SHALL calculate and display the stock cost required for one bond lot using the A-share 100-share purchase constraint.

#### Scenario: A raw share requirement is not a 100-share multiple

- GIVEN the theoretical shares required for one lot are 1,050
- WHEN placement cost is shown
- THEN the display uses 1,100 actual shares
- AND the cost equals actual shares multiplied by current stock price.

### Requirement: Placement score assumptions

The current placement score SHALL combine issue size, estimated tradable amount, and safety pad using the documented three-factor weights. The fixed 20 percent first-day premium is an assumption for comparison only and SHALL NOT be presented as verified return.

#### Scenario: A safety pad is shown

- GIVEN the system has required placement and stock fields
- WHEN it calculates safety pad
- THEN it identifies the 20 percent expected premium assumption
- AND does not imply the result proves a profitable or executable trade.

### Requirement: Placement eligibility evidence

The system SHALL distinguish a placement observation from a verified executable opportunity. A verified executable record requires issuer evidence for eligibility, record date, allocation terms, payment timing, and relevant announcement date and URL.

#### Scenario: A pending bond only has market and issuance fields

- GIVEN a bond has issue size, stock price, and a calculated score
- WHEN it lacks verified original-shareholder allocation evidence
- THEN the UI treats it as an observation or planning aid
- AND does not label it an executable guaranteed opportunity.

### Requirement: Placement timeline fidelity

The placement timeline SHALL render known stage dates and show missing dates explicitly. Notice-derived stage dates MAY be cached, and missing data for unsupported exchanges SHALL not be fabricated.

#### Scenario: An exchange has no usable announcement data

- GIVEN the announcement provider does not return a supported record
- WHEN the timeline is rendered
- THEN the affected stage remains unknown or is marked data-limited
- AND no inferred date is shown as factual.

## Known limitations

- Announcement enrichment may take significant time on a cold refresh because it scans notice pages serially.
- Some stage dates remain unavailable, including unsupported Beijing Stock Exchange records and notices beyond the configured scan depth.
