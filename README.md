# RiveAr Test Automation Framework (rivear-taf)

Python test automation framework built with pytest, targeting the **RiveAr**
e-commerce/SaaS application (React + FastAPI + PostgreSQL).

RiveAr is treated as an external System Under Test: this repository talks to
it over HTTP only and imports nothing from its source.

## Status

Framework foundation: an HTTP client, fixtures, one smoke suite. Everything
else is built incrementally on top of this - see [Roadmap](#roadmap).

## Structure

The framework is organized by layer - no empty scaffolding for layers that
don't have code yet.

- `core/` - framework-wide building blocks, one subpackage per layer:
  - `core/api/` - `ApiClient`, the one place that knows how to reach the API
  - `core/db/` - the SQLAlchemy connection setup for the SUT's Postgres
  - there is no `core/ui/`: Playwright's own `page` fixture already is the
    SUT-agnostic driver, so nothing generic was left to put there
- `api/` - everything specific to testing the HTTP API:
  - `api/clients/` - domain clients built on `core.api.api_client.ApiClient`
    (`AuthClient`, `AdminClient`, ...)
  - `api/models/` - Pydantic response contract models, one module per domain
- `db/` - everything specific to the SUT's database:
  - `db/models.py` - ORM models mirroring its tables, declared here rather
    than imported from the SUT
- `utils/` - shared assertion and reporting helpers (`assert_status_code`,
  `assert_error`, `step`, ...)
- `tests/` - test suites, split the same way:
  - `tests/conftest.py` - fixtures more than one suite needs
  - `tests/api/` - API test suites, `conftest.py`, and `tests/api/scenarios/`
  - `tests/db/` - DB test suites
  - `tests/ui/` - UI `conftest.py` and `tests/ui/scenarios/`; the suites and a
    top-level `ui/` for page objects arrive with the first implemented test

Page objects expose locators and actions; assertions stay in the test - the
same split as API clients returning responses that `utils` asserts on.
Locators prefer role and label over `data-testid` - see
[.claude/agents/ui-test-writer.md](.claude/agents/ui-test-writer.md) for the order.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

Requires the RiveAr stack running locally (`docker compose up` in the RiveAr
repo) with test-support routes enabled (any non-production `APP_ENV`). The UI
suite drives the front end the same stack serves on port 5173.

## Running

```bash
pytest
pytest -m smoke
pytest tests/api
pytest tests/db
pytest tests/ui
```

UI runs headless by default. To watch one, or to keep an artifact of a
failure:

```bash
pytest tests/ui --headed --slowmo 300
pytest tests/ui --screenshot only-on-failure --tracing retain-on-failure
```

```bash
allure serve reports/allure_results
```

## CI

GitHub Actions boots the SUT from source (Postgres + backend via its own
`docker-compose.yml`, migrated and seeded) and runs the suites against it -
see [.github/workflows/tests.yml](.github/workflows/tests.yml).

| Workflow | Trigger | Runs |
|----------|---------|------|
| Smoke | push/PR to `main`, or manually | API `-m smoke` + the whole DB suite |
| Regression | daily 03:00 UTC, or manually | the whole API suite (`-n 4`) + the whole DB suite |

Both share one SUT boot - it costs minutes, the tests cost seconds. Each run
writes a per-suite job summary and uploads the Allure/JUnit reports as a
build artifact.

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
| `base_url`      | session  | The front end's URL, from `.env`                 |
| `customer_tokens` | session | A token pair for the seeded CUSTOMER, over the API |
| `sign_in`       | function | Hands the browser a session, skipping the login form |

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
