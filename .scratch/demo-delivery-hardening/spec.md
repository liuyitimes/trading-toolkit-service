# Demo Delivery Hardening

Status: ready-for-agent

## Problem Statement

Trading Toolkit is a two-repository Demo: a Flask service supplies market and strategy data to a Vue Web application. Before this work, the production delivery path did not consistently protect management endpoints, constrain browser origins, enforce database migration, or stop a deployment when verification failed. API path drift could also reach the Web application unnoticed. The project must remain quick to iterate, without introducing application login, user authentication, or a Worker proxy.

## Solution

Provide a minimal, observable, repeatable delivery path. The public service exposes a small health endpoint; management operations are disabled unless explicitly enabled for local diagnosis; browser access is limited to configured origins; and request logs omit request and response bodies. Production starts only with PostgreSQL and current Alembic migrations. The service publishes a machine-readable HTTP endpoint matrix consumed by the Web repository. CI verifies the contract, tests, builds, deploys to Render Singapore, and checks health. All local development, tests, Docker validation, and delivery rehearsal run in WSL Ubuntu.

## User Stories

1. As a Demo visitor, I want the service health endpoint to return only a simple status, so that uptime checks reveal no operational configuration.
2. As a maintainer, I want management routes disabled in production, so that cache clearing, source switching, and API-log access are not public.
3. As a local developer, I want to opt in to management routes with an environment switch, so that diagnosis remains available without weakening production defaults.
4. As a Web user, I want the browser to call the service only from configured origins, so that cross-origin access is intentional.
5. As a privacy-conscious maintainer, I want request logs to retain only operational metadata, so that payloads and responses are not stored in service memory.
6. As a deployer, I want a production start to reject SQLite, so that containers never silently use ephemeral state.
7. As a deployer, I want migrations to run before the process accepts traffic, so that application code and database schema remain compatible.
8. As a developer, I want local SQLite to remain available, so that ordinary development and tests do not require a hosted database.
9. As a Web developer, I want a machine-readable API matrix, so that a route or method mismatch fails before release.
10. As a release owner, I want tests to finish before a Render deployment hook runs, so that failed verification cannot trigger deployment.
11. As a release owner, I want a health smoke check after deployment, so that a failed service start is visible immediately.
12. As an operator, I want optional Sentry reporting, so that production exceptions can be investigated without requiring the integration during early Demo work.
13. As a maintainer, I want dependency and static-analysis scans, so that routine supply-chain and code risks are visible in pull requests.
14. As a China-based Demo user, I want hosting limitations described accurately, so that global-edge hosting is not mistaken for guaranteed mainland acceleration.
15. As a project contributor, I want all local validation commands to run in WSL Ubuntu, so that the development and CI-like environment is consistent.
16. As a product owner, I want to defer authentication and login, so that the Demo remains small while the public operational boundary is still protected.

## Implementation Decisions

- The Demo delivery topology is Cloudflare Pages for the Web application and Render Singapore for the Flask API. The browser calls the configured API base URL directly; no Worker proxy is added.
- Mainland access is best effort only. The project does not claim mainland nodes, low latency, ICP compliance, or an SLA.
- `/healthz` is the public health contract. It returns the existing success envelope with only a status value; legacy public health compatibility must preserve this minimal response.
- Administrative health, source-switching, cache-clearing, and API-log routes require an explicit `ENABLE_ADMIN_API` opt-in. Production uses `false`.
- `CORS_ALLOWED_ORIGINS` is the sole configuration source for permitted browser origins. Credentials are not enabled.
- API logs retain request ID, method, path, status, and duration only. Request bodies, response bodies, and payload-derived log search are excluded.
- Local SQLite remains the default development state. Production requires a non-SQLite PostgreSQL `DATABASE_URL`; migrations are applied with Alembic before the service starts, and a failure aborts startup.
- Persisted Demo data is rebuildable. The project does not add scheduled backup, disaster recovery, or cross-region replication; destructive migrations require a manual export first.
- The HTTP endpoint matrix records stable API method and path definitions. Flask routes validate against it, and the Web consumer validates its declared API definitions against it.
- Render deployment follows verify, deploy-hook, then `/healthz` smoke-check. The main branch is protected outside the repository through review and required-check rules.
- Sentry is initialized only when its DSN is configured. Dependabot and CodeQL provide ongoing dependency and code scanning without automatic merges.
- Local development, test execution, Docker builds, containers, deployment rehearsal, and CI-like commands use WSL Ubuntu.

## Testing Decisions

- A good delivery test asserts observable behavior: status and response envelope, inaccessible management operations, permitted and rejected origins, route-method compatibility, a successful migration path, and an actual browser route rendering. It does not assert private helper calls or framework internals.
- The service API contract test is the primary boundary seam. It compares the endpoint matrix with Flask route registration, while focused service tests exercise health, administration defaults, CORS, and reduced logging behavior.
- The Web contract consumer is the matching seam. It reads the same matrix and verifies the API module method/path declarations, including path parameters.
- Existing Playwright smoke tests are used for market loading and the convertible placement workflow. Existing export tests verify the placement document remains usable.
- CI reproduces the important user-visible path with formatting checks for the delivery boundary, contract verification, build, browser smoke tests, deployment trigger, and health check.
- Docker image build and startup validation run in WSL Ubuntu or Render because they require the Docker daemon and production-like PostgreSQL configuration.

## Out of Scope

- Application login, user authentication, sessions, RBAC, and audit-platform features.
- A Cloudflare Worker API proxy.
- Prometheus, a centralized logging stack, automated database backups, disaster recovery, or historical-data recovery guarantees.
- Guaranteed China mainland performance, ICP filing, mainland hosting, or a production SLA.
- Automatic merging of dependency upgrades.

## Further Notes

External setup still requires platform credentials: Render needs PostgreSQL and environment variables; GitHub needs deployment secrets and branch protection; Cloudflare needs a Pages project and API credentials; Sentry remains optional. These are deployment-account operations, not values that can be invented in source control.
