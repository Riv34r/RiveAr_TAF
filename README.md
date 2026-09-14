# RiveAr Test Automation Framework (rivear-taf)

Python test automation framework built with pytest, targeting the **RiveAr**
e-commerce/SaaS application (React + FastAPI + PostgreSQL).

RiveAr is treated as an external System Under Test: this repository talks to
it over HTTP only and imports nothing from its source.

## Status

API, DB and UI layers are in place: seven API suites, DB suites for the rules
the schema enforces, and a first UI suite for logging in. Built incrementally -
see [Roadmap](#roadmap).

## Structure

The framework is organized by layer - no empty scaffolding for layers that
don't have code yet.

- `core/` - framework-wide building blocks, one subpackage per layer:
  - `core/api/` - `ApiClient`, the one place that knows how to reach the API
  - `core/db/` - the SQLAlchemy connection setup for the SUT's Postgres
  - `core/ui/` - `BasePage`, what every page object builds on: its page, its
    path, and `open()`
- `api/` - everything specific to testing the HTTP API:
  - `api/clients/` - domain clients built on `core.api.api_client.ApiClient`
    (`AuthClient`, `AdminClient`, ...)
  - `api/models/` - Pydantic response contract models, one module per domain
- `db/` - everything specific to the SUT's database:
  - `db/models.py` - ORM models mirroring its tables, declared here rather
    than imported from the SUT
- `ui/` - everything specific to driving the SUT's front end:
  - `ui/pages/` - page objects, one per screen
  - `ui/components/` - objects for components on more than one screen
- `utils/` - shared assertion and reporting helpers (`assert_status_code`,
  `assert_error`, `step`, ...)
- `tests/` - test suites, split the same way:
  - `tests/conftest.py` - fixtures more than one suite needs
  - `tests/api/` - API test suites, `conftest.py`, and `tests/api/scenarios/`
  - `tests/db/` - DB test suites and `tests/db/scenarios/`
  - `tests/ui/` - UI test suites, `conftest.py`, and `tests/ui/scenarios/`

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
build artifact. The UI suite doesn't run in CI yet.

## Fixtures

Shared by more than one suite - `tests/conftest.py`:

| Fixture | Scope | Purpose |
|---|---|---|
| `api_url` | session | Base URL + version prefix, from `.env` |
| `api` | session | Unauthenticated `ApiClient` |
| `auth_client` | session | `AuthClient` wrapping `api`, for `/auth/*` |
| `seed_manifest` | session | Seeded accounts, their shared password, and named seed fixtures |
| `customer` | session | The seeded CUSTOMER account, with its password |
| `db_session` | function | A database session rolled back after the test |
| `count_rows` | function | `count_rows(condition)` - how many rows match |

API suite - `tests/api/conftest.py`:

| Fixture | Scope | Purpose |
|---|---|---|
| `admin_client` | session | `AdminClient` authenticated as the seeded ADMIN |
| `run_id` | function | Unique tag for one test's disposable entities |
| `factory` | function | Creates disposable entities, cleaned up after |

UI suite - `tests/ui/conftest.py`: `base_url`, the front end's URL from `.env`,
and page objects reaching tests through fixtures named after their screen
(`login_page`) - or returned by the action that leads to them, like
`login_page.login(customer)` returning the `HomePage` when the login is
expected to succeed. Components such as the
navbar are reached through the page they're on - `home_page.navbar`.

## Test coverage

Test cases carry stable IDs via `@allure.tag(...)`, matching the scenario docs
in each suite's `scenarios/` folder. Docstrings are reserved for genuinely
important context, not the ID itself.

| Suite | IDs | Covers |
|---|---|---|
| `tests/api/test_health.py` | HLT-01..02 | API and database up, non-production environment |
| `tests/api/test_auth.py` | AUTH-001..031 | Register, login, refresh, logout, profile, password |
| `tests/api/test_admin.py` | ADMIN-001..020 | Users, audit logs |
| `tests/api/test_admin_roles.py` | ROLE-001..017 | Roles and permission grants |
| `tests/api/test_products.py` | PROD-001..040 | CRUD, soft delete, bulk operations, ETag/If-Match |
| `tests/api/test_inventory.py` | INV-001..021 | Listing, stock adjustments, transaction history |
| `tests/api/test_orders.py` | ORD-001..040 | Create, checkout, status machine, payments, idempotency |
| `tests/db/test_inventory.py` | DB-INV-01..05 | Generated columns, CHECKs, foreign key, cascade |
| `tests/db/test_orders.py` | DB-ORD-01..07 | Generated columns, CHECKs, cascade, RESTRICT, UNIQUE |
| `tests/ui/test_login.py` | UI-LOGIN-01 | Logging in through the form |

## Defects found

Real defects found in RiveAr while building tests against it are logged in
[BUGS.md](BUGS.md), with evidence, root cause and the guarding test.

## Code style

`black`, `isort`, `flake8` (line length 88):

```bash
pre-commit install
```

## Roadmap

| # | Increment | Adds | Status |
|---|-----------|------|--------|
| 1 | API foundation | `ApiClient`, fixtures, health suite, Allure/JUnit reporting | Done |
| 2 | API domain suites | Auth, admin and roles, products, inventory, orders | Done - cart and promotions not yet |
| 3 | Test data lifecycle | Factories + cleanup for suites that mutate state | Done |
| 4 | Database layer | Rules the schema enforces itself | Done |
| 5 | DB checks in API tests | Database assertions where the API's response can't show the state | Done |
| 6 | UI layer | Playwright, page objects, critical journeys | In progress - login |
| 7 | End-to-end | UI action -> API state -> DB truth | Planned |
| 8 | CI | GitHub Actions: boot the SUT, run suites, publish reports | Done for API and DB |
