# RiveAr Test Automation Framework (rivear-taf)

Python test automation framework built with pytest, targeting the **RiveAr**
e-commerce/SaaS application (React + FastAPI + PostgreSQL).

RiveAr is treated as an external System Under Test: this repository talks to
it over HTTP only and imports nothing from its source.

## Status

Framework foundation: an HTTP client, fixtures, one smoke suite. Everything
else is built incrementally on top of this - see [Roadmap](#roadmap).

## Structure

The framework is organized by layer. API and DB exist today; UI gets its
own `core/ui/`, `ui/`, and `tests/ui/` the same way once it starts (see
[Roadmap](#roadmap)) - no empty scaffolding for layers that don't have
code yet.

- `core/` - framework-wide building blocks, one subpackage per layer:
  - `core/api/` - `ApiClient`, the one place that knows how to reach the API
  - `core/db/` - TAF's own SQLAlchemy models and engine/session setup for
    the SUT's Postgres database (declared independently, not imported
    from the SUT - see `core/db/models.py`). A `db/` package (mirroring
    `api/clients/`) will hold reusable, composable query conditions under
    `db/queries/<domain>.py` once a scenario needs more than one - not
    created ahead of that need.
- `api/` - everything specific to testing the HTTP API:
  - `api/clients/` - domain clients built on `core.api.api_client.ApiClient`
    (`AuthClient`, `AdminClient`, ...)
  - `api/models/` - Pydantic response contract models, one module per domain
- `utils/` - shared assertion helpers (`assert_status_code`, `assert_error`, ...)
- `tests/` - test suites, split the same way:
  - `tests/api/` - API test suites, `conftest.py`, and `tests/api/scenarios/`
  - `tests/db/` - DB test suites and `conftest.py`

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Requires the RiveAr stack running locally (`docker compose up` in the RiveAr
repo) with test-support routes enabled (any non-production `APP_ENV`).

## Running

```bash
pytest
pytest -m smoke
pytest tests/api
pytest tests/db
```

```bash
allure serve reports/allure_results
```

## Fixtures

| Fixture         | Scope    | Purpose                                          |
|-----------------|----------|---------------------------------------------------|
| `api_url`       | session  | Base URL + version prefix, from `.env`           |
| `api`           | session  | Unauthenticated `ApiClient`                      |
| `auth_client`   | session  | `AuthClient` wrapping `api`, for `/auth/*`       |
| `seed_manifest` | session  | Seeded accounts and their shared password        |
| `customer`      | session  | The seeded CUSTOMER account                      |
| `admin_client`  | session  | `ApiClient` authenticated as the seeded ADMIN    |
| `run_id`        | function | Unique tag for one test's disposable entities    |
| `factory`       | function | Creates disposable entities, cleaned up after    |

## Test coverage

Test cases carry stable IDs via `@allure.tag(...)` (`HLT-*`, `AUTH-*`, ...).
Docstrings are reserved for genuinely important context, not the ID itself.

- `tests/api/test_health.py` - HLT-01/02
- `tests/api/test_auth.py` - AUTH-001..031 (register, login, refresh, logout, profile, password)

## Defects found

Real defects found in RiveAr while building tests against it are logged in
[BUGS.md](BUGS.md), with evidence, root cause and the guarding test.

## Code style

`black`, `isort`, `flake8` (line length 88):

```bash
pre-commit install
```

## Roadmap

| # | Increment | Adds |
|---|-----------|------|
| 1 | **API foundation** (current) | `ApiClient`, fixtures, health suite, Allure/JUnit reporting |
| 2 | API domain suites | Auth, orders, products, cart, promotions, RBAC |
| 3 | Test data lifecycle | Factories + cleanup for suites that mutate state |
| 4 | Database layer | Read-only verification of state the API only claims |
| 5 | API + DB integration | Checkout reserves stock, cancellation releases it |
| 6 | UI layer | Playwright, page objects, critical journeys |
| 7 | End-to-end | UI action -> API state -> DB truth |
| 8 | CI | GitHub Actions: boot the SUT, run suites, publish reports |
