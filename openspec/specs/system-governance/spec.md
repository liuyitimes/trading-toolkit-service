# System Governance Specification

## Purpose

Define the supported product boundary and the rules that keep the baseline specifications authoritative.

## Requirements

### Requirement: Supported module boundary

The project SHALL treat the Web application, Flask service, and backtest package as supported modules. The `trading-toolkit-mp` directory SHALL be excluded from routine maintenance and feature delivery.

#### Scenario: A feature changes a shared financial rule

- GIVEN a requested change affects a rule consumed by the Web application and service
- WHEN the change is planned
- THEN its OpenSpec change identifies both supported modules
- AND it does not require a mini-program update unless the user explicitly reactivates that module.

### Requirement: Baseline-first change planning

Medium or large behavior changes SHALL begin from an applicable baseline specification and SHALL be recorded as an OpenSpec delta before implementation.

#### Scenario: A public API field changes

- GIVEN a developer intends to add, remove, or change a public API field
- WHEN the work is planned
- THEN the change includes proposal, delta specification, design, tasks, compatibility handling, and verification.

### Requirement: Evidence precedence

When repository sources disagree, current executable code and tests SHALL take precedence over baseline specifications, which take precedence over current documentation and historical records.

#### Scenario: A historical plan conflicts with a route implementation

- GIVEN a plan names a retired data-source fallback
- WHEN a developer documents or extends the system
- THEN the developer uses the current direct-HTTP implementation as the behavioral baseline
- AND records the historical item only as superseded context.

### Requirement: Delivery state separation

Delivery reports SHALL distinguish implemented, verified, and operationally available states.

#### Scenario: A UI change builds locally

- GIVEN the frontend build succeeds
- WHEN the work is reported
- THEN the report identifies build success as verification evidence
- AND does not claim production availability without deployment and runtime evidence.
