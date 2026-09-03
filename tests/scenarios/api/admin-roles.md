# Admin Roles & Permissions API — Test Scenarios

Source of truth: `GET /openapi.json` (paths under `/api/v1/admin/roles`,
OpenAPI tag `admin-roles`) cross-checked against
`backend/app/services/role_service.py` and
`backend/app/api/routes/admin_roles.py` in the RiveAr App repository.

Split out from [admin.md](admin.md): the SUT tags this router separately
from `/admin/users` and `/admin/audit-logs` (`admin-roles` vs `admin`), and
it has its own, self-contained error vocabulary
(`ROLE_NOT_FOUND`, `PERMISSION_NOT_FOUND`, `PERMISSION_ALREADY_GRANTED`,
`PERMISSION_PROTECTED`, `UNKNOWN_PERMISSION`) that nothing else in the admin
surface uses. IDs use their own `ROLE-*` prefix, numbered sequentially from
001 within this file, rather than continuing admin.md's `ADMIN-*` sequence.

Endpoints in scope:

- `GET    /admin/roles`
- `GET    /admin/roles/permission-catalogue`
- `POST   /admin/roles/{role_id}/permissions`
- `DELETE /admin/roles/{role_id}/permissions/{permission_id}`

All four require `roles:manage`, enforced by the same `require_permission`
dependency as every other admin endpoint: missing/invalid token -> 401
(`TOKEN_MISSING`/`TOKEN_INVALID`), authenticated without the permission ->
403 `INSUFFICIENT_PERMISSIONS` with `details.required_any_of`. Covered once
here rather than per scenario - see ROLE-002/004.

---

### ROLE-001 — Listing roles returns each with its permissions

**Endpoint:** GET /api/v1/admin/roles
**Type:** Positive
**Priority:** Medium

**Expected Result:**
- Response status is 200.
- Each role has `id`, `name`, `permissions` (a list of `{id, name, description}`).

### ROLE-002 — Listing roles without `roles:manage` returns 403

**Endpoint:** GET /api/v1/admin/roles
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 403.
- `error.details.required_any_of` contains `"roles:manage"`.

### ROLE-003 — The permission catalogue lists every grantable permission

**Endpoint:** GET /api/v1/admin/roles/permission-catalogue
**Type:** Positive
**Priority:** Medium

**Objective:** This is the set `grant_permission` validates `name` against -
worth confirming it is non-empty and shaped as `{permission_name: description}`.

**Expected Result:**
- Response status is 200.
- Response is a non-empty mapping of permission name to description.

### ROLE-004 — The permission catalogue requires `roles:manage`

**Endpoint:** GET /api/v1/admin/roles/permission-catalogue
**Type:** Negative
**Priority:** Low

**Expected Result:**
- Response status is 403.

### ROLE-005 — Granting a permission a role does not yet have succeeds

**Endpoint:** POST /api/v1/admin/roles/{role_id}/permissions
**Type:** Positive
**Priority:** High

**Preconditions:**
- A role that does not currently hold the permission being granted.

**Expected Result:**
- Response status is 201.
- The returned role's `permissions` now includes the granted one.

### ROLE-006 — Granting a permission the role already has returns 409

**Endpoint:** POST /api/v1/admin/roles/{role_id}/permissions
**Type:** Negative
**Priority:** Medium

**Preconditions:**
- The role already holds the permission (grant it first, or use one the
  role is seeded with).

**Expected Result:**
- Response status is 409.
- `error.code` is `PERMISSION_ALREADY_GRANTED`.

### ROLE-007 — Granting an unrecognised permission name returns 422

**Endpoint:** POST /api/v1/admin/roles/{role_id}/permissions
**Type:** Validation
**Priority:** Medium

**Expected Result:**
- Response status is 422.
- `error.code` is `UNKNOWN_PERMISSION`.
- `error.details.allowed` lists the real permission catalogue.

### ROLE-008 — Granting a permission to an unknown role returns 404

**Endpoint:** POST /api/v1/admin/roles/{role_id}/permissions
**Type:** Negative
**Priority:** Low

**Expected Result:**
- Response status is 404.
- `error.code` is `ROLE_NOT_FOUND`.

### ROLE-009 — Revoking a permission a role holds succeeds

**Endpoint:** DELETE /api/v1/admin/roles/{role_id}/permissions/{permission_id}
**Type:** Positive
**Priority:** High

**Preconditions:**
- Grant a permission first (via ROLE-005 or directly), so there is
  something safe and non-protected to revoke.

**Expected Result:**
- Response status is 200.
- The returned role's `permissions` no longer includes it.

### ROLE-010 — `roles:manage` cannot be revoked from ADMIN

**Endpoint:** DELETE /api/v1/admin/roles/{role_id}/permissions/{permission_id}
**Type:** Negative / Security
**Priority:** High

**Objective:** `PROTECTED_ROLE_PERMISSIONS = {("ADMIN", "roles:manage")}` is a
single, deliberate, hardcoded exception: without it, revoking this
permission from ADMIN would leave nobody able to grant it back through the
API. This is the one case in the whole admin surface that a request cannot
undo by calling the API again - worth its own scenario rather than folding
into ROLE-009's happy path.

**Expected Result:**
- Response status is 409.
- `error.code` is `PERMISSION_PROTECTED`.
- The ADMIN role's `roles:manage` permission is unchanged (verify via
  `GET /admin/roles` or by confirming the acting admin can still call
  admin-role endpoints afterward).

### ROLE-011 — Revoking a permission a role does not hold returns 404

**Endpoint:** DELETE /api/v1/admin/roles/{role_id}/permissions/{permission_id}
**Type:** Negative
**Priority:** Low

**Objective:** Distinct from ROLE-012 - the role exists, but this specific
permission is not one of its own (e.g. a valid permission ID that belongs to
a *different* role).

**Expected Result:**
- Response status is 404.
- `error.code` is `PERMISSION_NOT_FOUND`.

### ROLE-012 — Revoking a permission from an unknown role returns 404

**Endpoint:** DELETE /api/v1/admin/roles/{role_id}/permissions/{permission_id}
**Type:** Negative
**Priority:** Low

**Expected Result:**
- Response status is 404.
- `error.code` is `ROLE_NOT_FOUND`.

### ROLE-013 — A malformed role_id (not a UUID) returns 422, not 404

**Endpoint:** POST /api/v1/admin/roles/{role_id}/permissions,
DELETE /api/v1/admin/roles/{role_id}/permissions/{permission_id}
**Type:** Validation
**Priority:** Low

**Objective:** Distinct from ROLE-008/012 - a syntactically invalid ID fails
at request validation before the role lookup ever runs, so it never reaches
`ROLE_NOT_FOUND`.

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.

### ROLE-014 — A malformed permission_id (not a UUID) returns 422, not 404

**Endpoint:** DELETE /api/v1/admin/roles/{role_id}/permissions/{permission_id}
**Type:** Validation
**Priority:** Low

**Objective:** Distinct from ROLE-011 - same reasoning as ROLE-013, applied
to `permission_id` instead.

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.

### ROLE-015 — An empty permission name is rejected at the schema level

**Endpoint:** POST /api/v1/admin/roles/{role_id}/permissions
**Type:** Validation
**Priority:** Low

**Objective:** Distinct from ROLE-007 - `""` fails `GrantPermissionRequest`'s
`min_length=1` before the catalogue is even consulted, so it is
`VALIDATION_ERROR`, not `UNKNOWN_PERMISSION`, and carries no
`details.allowed`.

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.
