# API Contract Specification

## Purpose

Define the supported HTTP contract between the Web application and Flask service.

## Requirements

### Requirement: Versioned response envelope

Business endpoints SHALL use the `/api/v1/` prefix and return a normalized envelope containing `success`, `data`, and `meta` on successful responses.

#### Scenario: A data request succeeds

- GIVEN a client requests a supported business endpoint
- WHEN the service obtains data or an allowed cache result
- THEN it returns `{ "success": true, "data": ..., "meta": { ... } }`
- AND `meta` communicates source, cache state, and update information where available.

### Requirement: Error contract

The service SHALL return a structured error response for invalid input, missing resources, and upstream failures. Clients SHALL surface an unsuccessful envelope as an error rather than treating it as domain data.

#### Scenario: A requested instrument does not exist

- GIVEN a client requests a detail endpoint with an unknown code
- WHEN no matching record is available
- THEN the service returns a not-found error response
- AND the Web client rejects the request instead of rendering an empty instrument as valid.

### Requirement: Compatibility routes

Legacy `/api/` routes MAY remain for explicitly supported compatibility endpoints, but new client behavior SHALL target `/api/v1/`.

#### Scenario: A new endpoint is introduced

- GIVEN a new service capability is added
- WHEN its route is designed
- THEN its canonical path uses `/api/v1/`
- AND no legacy alias is added unless a documented migration requires it.

### Requirement: User data authorization

Favorites, reminders, and settings endpoints SHALL require the service authentication mechanism and SHALL scope reads and writes to the authenticated `openid`.

#### Scenario: A user deletes a favorite

- GIVEN an authenticated request supplies a code and type
- WHEN the delete endpoint executes
- THEN only the matching favorite owned by that `openid` is deleted.

### Requirement: Client-server contract alignment

Web API client methods SHALL match implemented service routes and request methods. A mismatch SHALL be treated as a contract defect and tracked before relying on the capability.

#### Scenario: A Web client toggles a favorite

- GIVEN the current Web client exposes `POST /api/v1/user/favorites/toggle`
- WHEN the service does not implement that route
- THEN the capability is documented as a known contract gap
- AND a future change aligns client and service before presenting toggle behavior as supported.

## Known contract gaps

- The current Web `userApi.toggleFavorite` method targets `/api/v1/user/favorites/toggle`, while the service exposes `GET`, `POST`, and `DELETE /api/v1/user/favorites`. This baseline does not assert the toggle route exists.
- The Web client does not currently expose all service user, placement, or administrative endpoints. Absence of a client wrapper is not proof that the service endpoint is unsupported.
