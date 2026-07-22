# Operations and Delivery Specification

## Purpose

Define reproducible local development, verification, configuration, and deployment expectations for supported modules.

## Requirements

### Requirement: Local service development

The service SHALL be runnable from `trading-toolkit-service/cloudrun` with its declared Python dependencies and SHALL bind its local HTTP API to port 8080 unless configuration changes it.

#### Scenario: A developer starts the service locally

- GIVEN the service dependencies are installed
- WHEN the developer runs the Flask application from `cloudrun`
- THEN the API is reachable at the configured local address
- AND `/api/v1/admin/health` can report service, cache, source, and database status.

### Requirement: Local Web development

The Web application SHALL be runnable from `trading-toolkit-web` with declared Node dependencies, and its API base URL SHALL be configurable through build environment or local storage override.

#### Scenario: A developer points the Web app at a local service

- GIVEN the Flask service runs locally
- WHEN the developer supplies the local API base URL
- THEN the Web API client directs versioned requests to that service.

### Requirement: Environment configuration

The service SHALL document and honor `DATABASE_URL`, `REDIS_URL`, and `USE_MOCK` configuration. Mock mode SHALL be restricted to explicitly configured development or test use.

#### Scenario: Production cache is configured

- GIVEN `REDIS_URL` is configured in a deployment environment
- WHEN the service initializes its cache manager
- THEN it uses the configured Redis backend where reachable
- AND public response semantics remain unchanged.

### Requirement: Verification proportional to change

Backend changes SHALL include focused tests for affected logic and API behavior. Web changes SHALL include a production build and appropriate browser verification. Backtest changes SHALL run relevant pytest coverage.

#### Scenario: A cross-project API change is completed

- GIVEN a change affects a Flask endpoint and its Web consumer
- WHEN implementation is claimed complete
- THEN verification includes backend tests or endpoint checks, Web build, and the affected browser workflow
- AND the report separates these results from deployment availability.

### Requirement: Deployment boundaries

The service SHALL be deployable as the documented containerized CloudRun/CloudBase-compatible runtime, and the Web application SHALL be deployable as a static Vite build through its configured hosting workflow. Deployment configuration changes SHALL identify target environment, environment variables, and rollback procedure.

#### Scenario: A release changes an API base URL

- GIVEN a Web deployment needs a new service endpoint
- WHEN release configuration changes
- THEN the configured `VITE_API_BASE_URL` is verified against the deployed service
- AND rollback restores the prior known-good base URL.

### Requirement: No mini-program delivery work

Operational plans, CI, test matrices, and release checklists SHALL exclude `trading-toolkit-mp` unless the user explicitly changes its maintenance status.

#### Scenario: A release checklist is prepared

- GIVEN a supported release is planned
- WHEN verification targets are listed
- THEN they cover the Web application, service, and applicable backtest package
- AND do not require mini-program build or deployment steps.
