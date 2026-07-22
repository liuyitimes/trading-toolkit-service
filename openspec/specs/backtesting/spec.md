# Backtesting Specification

## Purpose

Define the supported backtesting engine boundaries and market-rule simulation behavior.

## Requirements

### Requirement: Layered backtest responsibilities

The backtest package SHALL separate market data, trading session, strategy, broker validation, exchange matching, portfolio accounting, engine orchestration, and performance metrics.

#### Scenario: A strategy places an order

- GIVEN a strategy receives a market bar
- WHEN it decides to trade
- THEN it creates an `Order` through the strategy interface
- AND it does not mutate cash or holdings directly.

### Requirement: Trading session rules

The engine SHALL model the documented China-market trading periods, skip weekends, and apply opening and closing auction handling.

#### Scenario: A bar falls in the midday break

- GIVEN the timestamp is outside a supported trading phase
- WHEN the engine processes data
- THEN it does not treat the time as continuous trading.

### Requirement: Order and capital validation

The broker SHALL enforce 100-share lot sizing, applicable price-limit bands, available funds including costs, and T+1 sell restrictions.

#### Scenario: A same-day purchase is sold

- GIVEN a position was bought on the current trading day
- WHEN a sell order is submitted before the next trading day
- THEN broker validation rejects the sell under T+1 rules.

### Requirement: Testable market-data boundary

The backtest engine SHALL remain testable with mock market data and fixtures when optional external market-data dependencies are unavailable.

#### Scenario: An environment lacks optional market-data dependencies

- GIVEN the runtime cannot load the optional historical-data provider
- WHEN unit tests execute with `MockMarketData`
- THEN broker, exchange, portfolio, session, and strategy tests can still validate core rules.
