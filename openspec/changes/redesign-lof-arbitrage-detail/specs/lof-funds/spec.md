## ADDED Requirements

### Requirement: LOF detail evidence and unavailable states

The LOF detail service SHALL return source, observation date, retrieval time, and freshness state for premium history, liquidity history, disclosed fund holdings, and risk inputs. It MUST distinguish fund portfolio holdings from a user's brokerage position; the service SHALL NOT claim either category when it only has total fund shares or modeled capital-flow data.

#### Scenario: Disclosed fund holdings are available

- **GIVEN** a dated official or manager-published portfolio disclosure is available
- **WHEN** the detail service returns holdings exposure
- **THEN** it includes the disclosure date, source, concentration metrics, and top holdings
- **AND THEN** it identifies the data as fund portfolio holdings rather than user holdings.

#### Scenario: A required historical or holdings input is unavailable

- **GIVEN** no verified source exists for a requested history or holdings input
- **WHEN** the detail service builds its response
- **THEN** it returns an explicit unavailable state and its source status
- **AND THEN** it does not substitute zeroes, mock history, or turnover-derived values.

### Requirement: LOF premium persistence, liquidity, and volatility risk disclosure

The system SHALL present premium persistence and settlement-window risk as dated analysis, not as a trade instruction. Persistence SHALL be calculated from persisted observed premium snapshots; liquidity SHALL include current and historical turnover or volume when available; volatility SHALL expose the measured window and inputs used for price, NAV, and premium variation.

#### Scenario: Sufficient observed history is available

- **GIVEN** the detail service has sufficient dated premium, price, NAV, and liquidity observations
- **WHEN** it builds the detail analysis
- **THEN** it reports the observation window, premium range or duration, liquidity comparison, and volatility measures
- **AND THEN** it separates current observed values from derived risk indicators.

#### Scenario: History is insufficient or simulated

- **GIVEN** the available history is shorter than the documented window or is sourced from a mock fallback
- **WHEN** the detail service builds premium persistence or risk fields
- **THEN** it returns the analysis as unavailable or simulated with the source status
- **AND THEN** it excludes that data from any decision label, risk grade, or expected-return conclusion.
