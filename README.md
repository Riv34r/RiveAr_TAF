# RiveAr Test Automation Framework (rivear-taf)

Python test automation framework built with pytest, targeting the **RiveAr**
e-commerce/SaaS application (React + FastAPI + PostgreSQL).

RiveAr is treated as an external System Under Test: this repository talks to
it over HTTP only and imports nothing from its source.

## Status

Framework foundation: an HTTP client, fixtures, one smoke suite. Everything
else is built incrementally on top of this - see [Roadmap](#roadmap).

## Structure

- `core/`  - `ApiClient` (the one place that knows how to reach the API) and
  domain clients built on top of it (`AuthClient`, ...)
- `models/` - Pydantic models for API objects (empty until a test needs one)
- `utils/` - shared assertion helpers (empty until one is shared)
- `tests/` - test suites and `conftest.py`

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
```

```bash
allure serve reports/allure_results
```

## Fixtures

| Fixture       | Scope   | Purpose                                    |
|---------------|---------|---------------------------------------------|
| `api_url`     | session | Base URL + version prefix, from `.env`     |
| `api`         | session | Unauthenticated `ApiClient`                |
| `auth_client` | session | `AuthClient` wrapping `api`, for `/auth/*` |

## Test coverage

Test cases carry stable IDs via `@allure.tag(...)` (`HLT-*`, `REG-*`, ...).
Docstrings are reserved for genuinely important context, not the ID itself.

- `tests/test_health.py` - HLT-01/02
- `tests/test_registration.py` - REG-01..05

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

<!-- test claude review -->
