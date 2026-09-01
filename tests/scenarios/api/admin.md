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
it per scenario - see ADMIN-002/003, ADMIN-012.

---

## Users

### ADMIN-001 — Listing users returns every account, paginated

**Endpoint:** GET /api/v1/admin/users
**Type:** Positive
**Priority:** High

**Preconditions:**
- Caller holds `users:manage`.

**Expected Result:**
- Response status is 200.
- Response has `items` and `pagination` (page, page_size, total, total_pages).

### ADMIN-002 — Listing users without the required permission returns 403

**Endpoint:** GET /api/v1/admin/users
**Type:** Negative
**Priority:** High

**Expected Result:**
- Response status is 403.
- `error.code` is `INSUFFICIENT_PERMISSIONS`.
- `error.details.required_any_of` contains `"users:manage"`.

### ADMIN-003 — Listing users with no token returns 401

**Endpoint:** GET /api/v1/admin/users
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 401.
- `error.code` is `TOKEN_MISSING`.

### ADMIN-004 — Getting a known user by ID succeeds

**Endpoint:** GET /api/v1/admin/users/{user_id}
**Type:** Positive
**Priority:** Medium

**Expected Result:**
- Response status is 200.
- `id`, `email`, `roles` match the requested account.

### ADMIN-005 — Getting an unknown user ID returns 404

**Endpoint:** GET /api/v1/admin/users/{user_id}
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 404.
- `error.code` is `USER_NOT_FOUND`.

### ADMIN-006 — Disabling a user's account takes effect immediately

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

### ADMIN-007 — Reassigning a user's roles replaces the previous set

**Endpoint:** PATCH /api/v1/admin/users/{user_id}
**Type:** Positive / State change
**Priority:** Medium

**Objective:** `roles` is a replacement, not an addition - the user ends up
with exactly the roles sent, not the union of old and new.

**Expected Result:**
- Response status is 200.
- `roles` in the response equals exactly what was sent, not a superset.

### ADMIN-008 — Setting an empty roles list is rejected

**Endpoint:** PATCH /api/v1/admin/users/{user_id}
**Type:** Validation
**Priority:** Low

**Objective:** A user must always hold at least one role;
`UserUpdateRequest.roles` enforces `min_length=1`.

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.

### ADMIN-009 — Updating an unknown user ID returns 404

**Endpoint:** PATCH /api/v1/admin/users/{user_id}
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 404.
- `error.code` is `USER_NOT_FOUND`.

### ADMIN-010 — An admin can disable their own account

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

---

## Audit logs

### ADMIN-011 — Listing audit logs returns recent entries, paginated

**Endpoint:** GET /api/v1/admin/audit-logs
**Type:** Positive
**Priority:** Medium

**Expected Result:**
- Response status is 200.
- Response has `items` and `pagination`.

### ADMIN-012 — Listing audit logs without `audit_logs:view` returns 403

**Endpoint:** GET /api/v1/admin/audit-logs
**Type:** Negative
**Priority:** Low

**Expected Result:**
- Response status is 403.
- `error.details.required_any_of` contains `"audit_logs:view"`.

### ADMIN-013 — Filtering by action returns only matching entries

**Endpoint:** GET /api/v1/admin/audit-logs
**Type:** Positive / Filtering
**Priority:** Medium

**Preconditions:**
- At least one log entry with a known `action` exists (e.g. trigger one via
  ADMIN-006, which writes `USER_STATUS_CHANGED`).

**Expected Result:**
- Response status is 200.
- Every returned item's `action` equals the requested filter value.

### ADMIN-014 — Granting a permission is itself recorded in the audit log

**Endpoint:** GET /api/v1/admin/audit-logs (after POST .../permissions)
**Type:** Positive / Integration
**Priority:** Medium

**Objective:** Cross-file scenario - ties ROLE-005 (in
[admin-roles.md](admin-roles.md)) to ADMIN-011: the audit trail is only
useful if administrative actions actually appear in it, not just
user-facing ones.

**Preconditions:**
- Grant a permission to a role (ROLE-005 in admin-roles.md).

**Expected Result:**
- `GET /admin/audit-logs?action=PERMISSION_GRANTED` includes an entry whose
  `entity_type` is `"role"` and whose `new_value` names the granted
  permission.
