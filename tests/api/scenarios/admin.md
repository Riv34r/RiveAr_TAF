# Admin API — Test Scenarios

Source of truth: `GET /openapi.json` (paths under `/api/v1/admin`, OpenAPI
tag `admin`) cross-checked against `backend/app/services/user_service.py`,
`backend/app/api/routes/admin_users.py`,
`backend/app/api/routes/admin_audit_logs.py`, and
`backend/app/dependencies/auth.py` in the RiveAr App repository.

Role and permission management (`/admin/roles/*`, tagged `admin-roles` in
the SUT's own OpenAPI spec) is a separate, self-contained domain with its
own error vocabulary - see [admin-roles.md](admin-roles.md).

Endpoints in scope:

- `GET   /admin/users`
- `GET   /admin/users/{user_id}`
- `PATCH /admin/users/{user_id}`
- `GET   /admin/audit-logs`

All four require a permission (`users:manage` or `audit_logs:view`),
enforced by the same `require_permission` dependency: missing/invalid token
-> 401 (`TOKEN_MISSING`/`TOKEN_INVALID`), authenticated without the
permission -> 403 `INSUFFICIENT_PERMISSIONS` with `details.required_any_of`.
Each endpoint group below covers that boundary once rather than repeating
it per scenario - see ADMIN-005/003, ADMIN-017.

---

## Permission boundary

### ADMIN-001 — Every admin endpoint requires authentication

**Endpoint:** all four - GET/PATCH /admin/users, GET /admin/users/{id},
GET /admin/audit-logs
**Type:** Negative / Security
**Priority:** High

**Objective:** `ADMIN-006` only proved the mechanism works on one
endpoint (`list_users`). That's sound for "does `require_permission`
behave correctly," but not for "is every route actually wired to it" -
a route missing its `Depends(...)` entirely is a real, distinct failure
mode a black-box test can only catch by calling that specific route.
Parametrized rather than four near-identical tests. Also worth noting:
`list_audit_logs` requires a different permission (`audit_logs:view`)
than the other three (`users:manage`) - a genuinely separate dependency
instance, not just the same check repeated.

**Expected Result:**
- Every endpoint, called with no token, returns 401 `TOKEN_MISSING`.

---

## Response schema

### ADMIN-002 — Listing users response matches the UserResponse schema

**Endpoint:** GET /api/v1/admin/users
**Type:** Positive / Contract
**Priority:** Medium

**Objective:** Full-shape validation via `api.models.common.PaginatedResponse`
+ `api.models.auth.UserResponse` (Pydantic) - catches drift in fields no
existing scenario asserts on individually.

**Expected Result:**
- Response status is 200.
- `PaginatedResponse[UserResponse].model_validate(response.json())` raises
  no `ValidationError`; `items` is non-empty (seeded accounts guarantee
  this).

### ADMIN-003 — Listing audit logs response matches the AuditLogResponse schema

**Endpoint:** GET /api/v1/admin/audit-logs
**Type:** Positive / Contract
**Priority:** Medium

**Preconditions:**
- A throwaway customer, disabled by the admin (guarantees at least one
  matching entry - an empty `items` list would validate trivially without
  ever exercising `AuditLogResponse`'s fields).

**Expected Result:**
- Response status is 200.
- `PaginatedResponse[AuditLogResponse].model_validate(response.json())`
  raises no `ValidationError`; `items` is non-empty.

---

## Users

### ADMIN-004 — Listing users returns every account, paginated

**Endpoint:** GET /api/v1/admin/users
**Type:** Positive
**Priority:** High

**Preconditions:**
- Caller holds `users:manage`.

**Expected Result:**
- Response status is 200.
- Response has `items` and `pagination` (page, page_size, total, total_pages).

### ADMIN-005 — Listing users without the required permission returns 403

**Endpoint:** GET /api/v1/admin/users
**Type:** Negative
**Priority:** High

**Expected Result:**
- Response status is 403.
- `error.code` is `INSUFFICIENT_PERMISSIONS`.
- `error.details.required_any_of` contains `"users:manage"`.

### ADMIN-006 — Listing users with no token returns 401

**Endpoint:** GET /api/v1/admin/users
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 401.
- `error.code` is `TOKEN_MISSING`.

### ADMIN-007 — Getting a known user by ID succeeds

**Endpoint:** GET /api/v1/admin/users/{user_id}
**Type:** Positive
**Priority:** Medium

**Expected Result:**
- Response status is 200.
- `id`, `email`, `roles` match the requested account.

### ADMIN-008 — Getting an unknown user ID returns 404

**Endpoint:** GET /api/v1/admin/users/{user_id}
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 404.
- `error.code` is `USER_NOT_FOUND`.

### ADMIN-009 — Disabling a user's account takes effect immediately

**Endpoint:** PATCH /api/v1/admin/users/{user_id}
**Type:** Positive / State change
**Priority:** High

**Objective:** `is_active: false` is not just a flag in the response - the
account can no longer authenticate afterward.

**Preconditions:**
- A throwaway customer created via the factory.

**Expected Result:**
- Response status is 200, `is_active: false`.
- A subsequent login with that account's real credentials returns 401
  `USER_DISABLED`.

### ADMIN-010 — Reassigning a user's roles replaces the previous set

**Endpoint:** PATCH /api/v1/admin/users/{user_id}
**Type:** Positive / State change
**Priority:** Medium

**Objective:** `roles` is a replacement, not an addition - the user ends up
with exactly the roles sent, not the union of old and new.

**Expected Result:**
- Response status is 200.
- `roles` in the response equals exactly what was sent, not a superset.

### ADMIN-011 — Setting an empty roles list is rejected

**Endpoint:** PATCH /api/v1/admin/users/{user_id}
**Type:** Validation
**Priority:** Low

**Objective:** A user must always hold at least one role;
`UserUpdateRequest.roles` enforces `min_length=1`.

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.

### ADMIN-012 — Updating an unknown user ID returns 404

**Endpoint:** PATCH /api/v1/admin/users/{user_id}
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 404.
- `error.code` is `USER_NOT_FOUND`.

### ADMIN-013 — An admin can disable their own account

**Endpoint:** PATCH /api/v1/admin/users/{user_id}
**Type:** Edge case
**Priority:** Medium

**Objective:** `update_user` applies no special case for `user_id == actor.id`
- an admin disabling or demoting themselves is accepted the same as doing it
to anyone else. Worth pinning down as a deliberate observation, not
discovering it by accident: this is a self-lockout path with no
confirmation step, and there is a real difference between "the API allows
it" (true today) and "the API should allow it" (a product decision, not
this suite's to make).

**Preconditions:**
- A throwaway admin-equivalent account, not the shared seeded admin (this
  must never leave the seeded ADMIN account disabled for the rest of the
  suite or other parallel workers).

**Expected Result:**
- Response status is 200; the account's own `is_active` becomes `false` (or
  its roles no longer include ADMIN, depending on which field is exercised).
- No special error or confirmation step is required by the API.

### ADMIN-014 — A malformed user_id (not a UUID) returns 422, not 404

**Endpoint:** GET /api/v1/admin/users/{user_id}
**Type:** Validation
**Priority:** Low

**Objective:** Distinct from ADMIN-008 - a syntactically invalid ID fails at
request validation before the lookup ever runs, so it never reaches
`USER_NOT_FOUND`.

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.

### ADMIN-015 — Setting an unrecognised role name is rejected

**Endpoint:** PATCH /api/v1/admin/users/{user_id}
**Type:** Validation
**Priority:** Low

**Objective:** Distinct from ADMIN-011 - a role name outside
`{ADMIN, MANAGER, SUPPORT, CUSTOMER}` fails Pydantic enum validation, not the
`min_length=1` check.

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.

---

## Audit logs

### ADMIN-016 — Listing audit logs returns recent entries, paginated

**Endpoint:** GET /api/v1/admin/audit-logs
**Type:** Positive
**Priority:** Medium

**Expected Result:**
- Response status is 200.
- Response has `items` and `pagination`.

### ADMIN-017 — Listing audit logs without `audit_logs:view` returns 403

**Endpoint:** GET /api/v1/admin/audit-logs
**Type:** Negative
**Priority:** Low

**Expected Result:**
- Response status is 403.
- `error.details.required_any_of` contains `"audit_logs:view"`.

### ADMIN-018 — Filtering by action returns only matching entries

**Endpoint:** GET /api/v1/admin/audit-logs
**Type:** Positive / Filtering
**Priority:** Medium

**Preconditions:**
- At least one log entry with a known `action` exists (e.g. trigger one via
  ADMIN-009, which writes `USER_STATUS_CHANGED`).

**Expected Result:**
- Response status is 200.
- Every returned item's `action` equals the requested filter value.

### ADMIN-019 — Granting a permission is itself recorded in the audit log

**Endpoint:** GET /api/v1/admin/audit-logs (after POST .../permissions)
**Type:** Positive / Integration
**Priority:** Medium

**Objective:** Cross-file scenario - ties ROLE-007 (in
[admin-roles.md](admin-roles.md)) to ADMIN-016: the audit trail is only
useful if administrative actions actually appear in it, not just
user-facing ones.

**Preconditions:**
- Grant a permission to a role (ROLE-007 in admin-roles.md).

**Expected Result:**
- `GET /admin/audit-logs?action=PERMISSION_GRANTED` includes an entry whose
  `entity_type` is `"role"` and whose `new_value` names the granted
  permission.

### ADMIN-020 — Combining audit log filters narrows the result, not widens it

**Endpoint:** GET /api/v1/admin/audit-logs
**Type:** Positive / Filtering
**Priority:** Medium

**Objective:** Filters are ANDed, not ORed. `action` alone and `action` +
`entity_id` together must not return the same count when more than one
entity has that action logged against it.

**Preconditions:**
- Two throwaway customers, both disabled by the same admin (two
  `USER_STATUS_CHANGED` entries, different `entity_id`).

**Expected Result:**
- Response status is 200.
- `?action=USER_STATUS_CHANGED` alone returns entries for both customers.
- `?action=USER_STATUS_CHANGED&entity_id=<first customer's id>` returns only
  the one entry matching both filters.

