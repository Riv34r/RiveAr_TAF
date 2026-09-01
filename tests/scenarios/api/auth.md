# Auth API — Test Scenarios

Source of truth: `GET /openapi.json` (paths under `/api/v1/auth`) cross-checked
against `backend/app/services/auth_service.py`,
`backend/app/dependencies/auth.py`, and `backend/app/schemas/auth.py` in the
RiveAr App repository. Every status code and error code below is taken
directly from that code, not inferred.

Endpoints in scope:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `PATCH /auth/me`
- `POST /auth/change-password`

---

## Register

### AUTH-001 — Registering with valid details creates a customer

**Endpoint:** POST /api/v1/auth/register
**Type:** Positive
**Priority:** High

**Objective:** A new account is created with the CUSTOMER role and is
immediately usable — no separate login step required.

**Preconditions:**
- Email not already registered.

**Expected Result:**
- Response status is 201.
- Response contains `access_token`, `refresh_token`, `token_type: "bearer"`, `expires_in > 0`.
- The returned access token authenticates on `GET /auth/me`, reporting `roles: ["CUSTOMER"]` and `is_active: true`.

### AUTH-002 — Registering with an already-registered email is rejected

**Endpoint:** POST /api/v1/auth/register
**Type:** Negative
**Priority:** High

**Objective:** Email uniqueness is enforced.

**Preconditions:**
- An account with the given email already exists (e.g. a seeded account).

**Expected Result:**
- Response status is 409.
- `error.code` is `EMAIL_ALREADY_REGISTERED`.

### AUTH-003 — Registering with a malformed email is rejected

**Endpoint:** POST /api/v1/auth/register
**Type:** Validation
**Priority:** Medium

**Objective:** Email format is validated before any account is created.

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.
- No account is created (a later register with the corrected email succeeds).

### AUTH-004 — Password strength rules are enforced

**Endpoint:** POST /api/v1/auth/register
**Type:** Validation / Boundary
**Priority:** High

**Objective:** A password must contain at least one letter and one digit, and
be at least 8 characters.

**Preconditions:** Parametrized — each case is independent:
- All-lowercase, no digit (e.g. `alllowercase`)
- All-digits, no letter (e.g. `12345678`)
- Below the 8-character floor (e.g. `short1`)

**Expected Result:**
- Response status is 422 for every case.
- `error.code` is `VALIDATION_ERROR`.

### AUTH-005 — A missing required field is rejected

**Endpoint:** POST /api/v1/auth/register
**Type:** Validation
**Priority:** Medium

**Objective:** `email`, `password`, and `full_name` are all required.

**Preconditions:** Parametrized over the three fields — each case omits exactly one.

**Expected Result:**
- Response status is 422 for every case.
- `error.code` is `VALIDATION_ERROR`.

---

## Login

### AUTH-006 — Logging in with valid credentials returns a token pair

**Endpoint:** POST /api/v1/auth/login
**Type:** Positive
**Priority:** High

**Objective:** A correct email/password pair authenticates successfully.

**Preconditions:**
- An active account with a known password exists.

**Expected Result:**
- Response status is 200.
- Response contains a usable `access_token` and `refresh_token`.
- `last_login_at` on the account is updated (verifiable via `GET /auth/me` after login, or DB).

### AUTH-007 — Logging in with a wrong password is rejected

**Endpoint:** POST /api/v1/auth/login
**Type:** Negative
**Priority:** High

**Expected Result:**
- Response status is 401.
- `error.code` is `INVALID_CREDENTIALS`.

### AUTH-008 — An unknown email is indistinguishable from a wrong password

**Endpoint:** POST /api/v1/auth/login
**Type:** Negative / Security
**Priority:** High

**Objective:** The API must not let a caller enumerate registered accounts by
comparing the response for "unknown email" against "known email, wrong
password."

**Expected Result:**
- Both cases return the same status (401) and the same `error.code`
  (`INVALID_CREDENTIALS`).

### AUTH-009 — Logging in to a disabled account is rejected

**Endpoint:** POST /api/v1/auth/login
**Type:** Negative
**Priority:** Medium

**Preconditions:**
- An account exists with correct credentials but `is_active: false`. The seed
  data has no pre-disabled user (every seeded account is `is_active: true`),
  so build one: create a throwaway customer via `POST /test/factory/customer`,
  then disable it as an admin via `PATCH /admin/users/{user_id}` with
  `{"is_active": false}`.

**Expected Result:**
- Response status is 401.
- `error.code` is `USER_DISABLED`.

### AUTH-010 — A malformed login request is rejected

**Endpoint:** POST /api/v1/auth/login
**Type:** Validation
**Priority:** Low

**Preconditions:** Parametrized — missing `email`, missing `password`, and an empty body.

**Expected Result:**
- Response status is 422 for every case.
- `error.code` is `VALIDATION_ERROR`.

---

## Refresh

### AUTH-011 — A valid refresh token rotates into a new token pair

**Endpoint:** POST /api/v1/auth/refresh
**Type:** Positive
**Priority:** High

**Objective:** Refresh tokens are single-use (rotation), not just renewable.

**Preconditions:**
- A valid, unused refresh token from a prior login/register.

**Expected Result:**
- Response status is 200.
- The returned `refresh_token` differs from the one submitted.
- The new access token authenticates successfully.

### AUTH-012 — A refresh token cannot be reused after rotation

**Endpoint:** POST /api/v1/auth/refresh
**Type:** Negative / Security
**Priority:** High

**Objective:** If a refresh token leaks, it is only useful until its owner
next refreshes.

**Preconditions:**
- A refresh token that has already been used once (per AUTH-011).

**Expected Result:**
- Response status is 401.
- `error.code` is `TOKEN_REVOKED`.

### AUTH-013 — An expired refresh token is rejected

**Endpoint:** POST /api/v1/auth/refresh
**Type:** Negative
**Priority:** Medium

**Blocker:** No API-only way to produce this precondition exists yet.
`POST /test/token` mints a short-TTL *access* token only — there is no
refresh-token equivalent, and waiting out the real
`REFRESH_TOKEN_EXPIRE_DAYS` (7 days) is not viable in a test suite. Testing
this would currently mean reaching into the database to backdate a
`refresh_tokens.expires_at` row, which this framework deliberately avoids
(tests go through the API, not around it). Options: ask for a
`POST /test/token`-style endpoint for refresh tokens on the SUT side, or
accept this scenario as DB-layer-only / manual for now.

**Preconditions:**
- A refresh token past its expiry (`REFRESH_TOKEN_EXPIRE_DAYS`).

**Expected Result:**
- Response status is 401.
- `error.code` is `TOKEN_EXPIRED`.

### AUTH-014 — A malformed refresh token is rejected

**Endpoint:** POST /api/v1/auth/refresh
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 401.
- `error.code` is `TOKEN_INVALID`.

### AUTH-015 — Refreshing as a since-disabled user is rejected

**Endpoint:** POST /api/v1/auth/refresh
**Type:** Negative
**Priority:** Low

**Preconditions:**
- Order matters: log in first to obtain the refresh token, *then* disable
  the account (same factory + admin-PATCH approach as AUTH-009). Disabling
  before login would fail at the login step instead of testing this path.

**Expected Result:**
- Response status is 401.
- `error.code` is `USER_DISABLED`.

---

## Logout

### AUTH-016 — Logging out revokes the refresh token

**Endpoint:** POST /api/v1/auth/logout
**Type:** Positive
**Priority:** High

**Expected Result:**
- Response status is 204.
- The same refresh token subsequently fails on `POST /auth/refresh` with `TOKEN_REVOKED`.

### AUTH-017 — Logout is idempotent for an already-unusable token

**Endpoint:** POST /api/v1/auth/logout
**Type:** Positive / Edge case
**Priority:** Medium

**Objective:** Calling logout twice, or with an already-expired token, must
not error — the caller's intent ("I am logged out") is already satisfied.

**Preconditions:** Parametrized — an already-revoked token, and a genuinely expired token.

**Expected Result:**
- Response status is 204 in both cases (never 401 for these two).

### AUTH-018 — A malformed refresh token on logout is rejected

**Endpoint:** POST /api/v1/auth/logout
**Type:** Negative
**Priority:** Low

**Objective:** Unlike an expired/revoked token, a structurally invalid token
is a client error, not a no-op.

**Expected Result:**
- Response status is 401.
- `error.code` is `TOKEN_INVALID`.

---

## Get current user

### AUTH-019 — A valid access token returns the caller's identity

**Endpoint:** GET /api/v1/auth/me
**Type:** Positive
**Priority:** High

**Expected Result:**
- Response status is 200.
- `id`, `email`, `full_name`, `roles`, `permissions`, `is_active` match the authenticated account.

### AUTH-020 — No token is rejected

**Endpoint:** GET /api/v1/auth/me
**Type:** Negative
**Priority:** High

**Expected Result:**
- Response status is 401.
- `error.code` is `TOKEN_MISSING`.

### AUTH-021 — A malformed access token is rejected

**Endpoint:** GET /api/v1/auth/me
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 401.
- `error.code` is `TOKEN_INVALID`.

### AUTH-022 — An expired access token is rejected

**Endpoint:** GET /api/v1/auth/me
**Type:** Negative
**Priority:** High

**Preconditions:**
- A token minted with a short TTL via the SUT's test-support endpoint (`POST /test/token`), now past expiry.

**Expected Result:**
- Response status is 401.
- `error.code` is `TOKEN_EXPIRED`.

### AUTH-023 — A token for a since-disabled user is rejected

**Endpoint:** GET /api/v1/auth/me
**Type:** Negative
**Priority:** Low

**Objective:** `is_active` is checked on every request, not only at login —
an access token issued while the account was active must stop working the
moment the account is disabled, without waiting for the token to expire.

**Preconditions:**
- Obtain a valid access token first (login), *then* disable the account
  (factory + admin-PATCH, as in AUTH-009). Reuse the same token afterward.

**Expected Result:**
- Response status is 401.
- `error.code` is `USER_DISABLED`.

---

## Update profile

### AUTH-024 — A valid full_name update succeeds

**Endpoint:** PATCH /api/v1/auth/me
**Type:** Positive
**Priority:** Medium

**Expected Result:**
- Response status is 200.
- `full_name` in the response reflects the new value.
- A subsequent `GET /auth/me` reflects the same change.

### AUTH-025 — Updating the profile without authentication is rejected

**Endpoint:** PATCH /api/v1/auth/me
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 401 (`TOKEN_MISSING` with no header, `TOKEN_INVALID` with a malformed one).

### AUTH-026 — An invalid full_name is rejected

**Endpoint:** PATCH /api/v1/auth/me
**Type:** Validation / Boundary
**Priority:** Low

**Preconditions:** Parametrized — an empty string, and a string over 255 characters.

**Expected Result:**
- Response status is 422 for both cases.
- `error.code` is `VALIDATION_ERROR`.

---

## Change password

### AUTH-027 — Changing the password with the correct current password succeeds

**Endpoint:** POST /api/v1/auth/change-password
**Type:** Positive
**Priority:** High

**Expected Result:**
- Response status is 204.
- A subsequent login with the *old* password fails (`INVALID_CREDENTIALS`).
- A login with the *new* password succeeds.

### AUTH-028 — Changing the password with the wrong current password is rejected

**Endpoint:** POST /api/v1/auth/change-password
**Type:** Negative
**Priority:** High

**Expected Result:**
- Response status is 401.
- `error.code` is `INVALID_CREDENTIALS`.
- The account's password is unchanged (old password still logs in).

### AUTH-029 — A weak new password is rejected

**Endpoint:** POST /api/v1/auth/change-password
**Type:** Validation
**Priority:** Medium

**Objective:** The same strength rule as registration (letter + digit, 8+
chars) applies to `new_password`.

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.
- The account's password is unchanged.

### AUTH-030 — Changing the password without authentication is rejected

**Endpoint:** POST /api/v1/auth/change-password
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 401 (`TOKEN_MISSING` or `TOKEN_INVALID` depending on what was sent).
