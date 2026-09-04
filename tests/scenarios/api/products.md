# Products API — Test Scenarios

Source of truth: `GET /openapi.json` (paths under `/api/v1/products`, OpenAPI
tag `products`) cross-checked against `backend/app/services/product_service.py`,
`backend/app/repositories/product_repository.py`,
`backend/app/api/routes/products.py`, and `backend/app/core/sorting.py` in
the RiveAr App repository.

Out of scope for this file, deliberately:

- `POST /products/bulk` — separate transaction semantics (atomic/best_effort),
  its own scenario set.
- ETag / `If-Match` precondition testing (missing header -> 428, stale
  version -> 412, concurrent-write races). `PUT`/`DELETE` below use a valid
  `If-Match` as an unavoidable precondition to reach the endpoint at all, but
  optimistic-concurrency behaviour itself is a separate scenario set.

Endpoints in scope:

- `GET    /products`
- `GET    /products/{product_id}`
- `POST   /products`
- `PUT    /products/{product_id}`
- `DELETE /products/{product_id}`
- `POST   /products/{product_id}/restore`

`GET` endpoints are public (anonymous callers allowed). `POST`/`PUT`/`DELETE`/
`restore` require `products:manage`, enforced by the same `require_permission`
dependency as the admin surface: missing/invalid token -> 401
(`TOKEN_MISSING`/`TOKEN_INVALID`), authenticated without the permission ->
403 `INSUFFICIENT_PERMISSIONS`. Covered once here rather than per endpoint -
see PROD-012.

---

## Listing

### PROD-001 — Listing products returns paginated results

**Endpoint:** GET /api/v1/products
**Type:** Positive
**Priority:** High

**Preconditions:**
- No authentication (public endpoint).

**Expected Result:**
- Response status is 200.
- Response has `items` and `pagination` (page, page_size, total, total_pages).

### PROD-002 — Default listing includes inactive products

**Endpoint:** GET /api/v1/products
**Type:** Positive / Edge case
**Priority:** Medium

**Objective:** No `status` filter is applied unless the caller passes one -
worth pinning down as a deliberate observation: the default catalogue can
list products a shopper cannot actually buy (ordering one is refused with
`PRODUCT_INACTIVE` elsewhere). The API behaves as specified; this documents
current behaviour rather than asserting it is desirable.

**Preconditions:**
- A throwaway inactive product via the factory (`is_active: false`).

**Expected Result:**
- Response status is 200.
- The inactive product's ID appears in the unfiltered `items`.

### PROD-003 — Filtering by status=active returns only active products

**Endpoint:** GET /api/v1/products?status=active
**Type:** Positive / Filtering
**Priority:** Medium

**Preconditions:**
- A throwaway inactive product via the factory.

**Expected Result:**
- Response status is 200.
- Every returned item's `is_active` is `true`; the inactive product's ID is
  absent.

### PROD-004 — An invalid sort_by returns 422 with the allowed values in the message

**Endpoint:** GET /api/v1/products?sort_by=...
**Type:** Validation
**Priority:** Low

**Objective:** `resolve_sort` puts the allowed columns in `error.message`
prose, not `error.details` - a client reacting to this programmatically has
to parse English. Recorded as a deliberate assertion of current behaviour
(see `BUGS.md` OBS-003), not a claim it is ideal.

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.
- `error.message` names at least one real sortable field (e.g. `price`).

### PROD-005 — Searching by name or description returns matching products

**Endpoint:** GET /api/v1/products?search=...
**Type:** Positive / Filtering
**Priority:** Medium

**Preconditions:**
- A throwaway product via the factory with a distinctive, unique `name`.

**Expected Result:**
- Response status is 200.
- The throwaway product's ID appears in `items`; searching for an
  unrelated, never-used term does not return it.

### PROD-006 — Combining category, price, and rating filters narrows the result

**Endpoint:** GET /api/v1/products?category_id=...&min_price=...&max_price=...
**Type:** Positive / Filtering
**Priority:** Medium

**Objective:** All four (`category_id`, `min_price`, `max_price`,
`min_rating`) are the same mechanical WHERE-clause pattern - one scenario
combining `min_price`/`max_price` is enough to prove the mechanism works.

**Expected Result:**
- Response status is 200.
- Response is non-empty.
- Every returned item's `price` falls within `min_price`/`max_price`.

### PROD-007 — include_deleted is ignored for non-manager callers

**Endpoint:** GET /api/v1/products?include_deleted=true
**Type:** Negative / Security
**Priority:** Medium

**Objective:** The flag is silently dropped rather than rejected for callers
without `products:manage` - worth confirming it fails closed (no
soft-deleted products leak to a public/customer caller) rather than
erroring.

**Preconditions:**
- A throwaway soft-deleted product.

**Expected Result:**
- Response status is 200 (not 403 - the flag is ignored, not rejected).
- The soft-deleted product's ID is absent from `items`.

---

## Get by ID

### PROD-008 — Getting a known product by ID succeeds

**Endpoint:** GET /api/v1/products/{product_id}
**Type:** Positive
**Priority:** High

**Expected Result:**
- Response status is 200.
- `id`, `sku`, `name`, `price` match the requested product.

### PROD-009 — Getting an unknown product ID returns 404

**Endpoint:** GET /api/v1/products/{product_id}
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 404.
- `error.code` is `PRODUCT_NOT_FOUND`.

### PROD-010 — A soft-deleted product is hidden from the public but visible to managers

**Endpoint:** GET /api/v1/products/{product_id}
**Type:** Positive / Negative
**Priority:** Medium

**Preconditions:**
- A throwaway product, soft-deleted (see PROD-019 for the delete call
  itself).

**Expected Result:**
- An anonymous/customer caller gets 404 `PRODUCT_NOT_FOUND`.
- A manager/admin caller gets 200, with `deleted_at` set.

---

## Create

### PROD-011 — Creating a product with valid data succeeds

**Endpoint:** POST /api/v1/products
**Type:** Positive
**Priority:** High

**Objective:** Also confirms the documented side effect - a zero-stock
inventory record is created alongside the product, so it is immediately
listable/gettable rather than erroring on a missing inventory join.

**Expected Result:**
- Response status is 201.
- Response echoes the submitted fields.
- `available_stock` is `0`, not `null` or missing.

### PROD-012 — Creating a product without products:manage returns 403

**Endpoint:** POST /api/v1/products
**Type:** Negative
**Priority:** High

**Expected Result:**
- Response status is 403.
- `error.code` is `INSUFFICIENT_PERMISSIONS`.

### PROD-013 — Creating a product with a duplicate SKU returns 409

**Endpoint:** POST /api/v1/products
**Type:** Negative
**Priority:** Medium

**Preconditions:**
- An existing product's `sku` (e.g. a throwaway product created moments
  before).

**Expected Result:**
- Response status is 409.
- `error.code` is `SKU_ALREADY_EXISTS`.

### PROD-014 — A discount_price at or above price is rejected

**Endpoint:** POST /api/v1/products
**Type:** Validation
**Priority:** Medium

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.

### PROD-015 — An unknown category_id is rejected

**Endpoint:** POST /api/v1/products
**Type:** Validation
**Priority:** Low

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.

---

## Update

### PROD-016 — A partial update only changes the fields sent

**Endpoint:** PUT /api/v1/products/{product_id}
**Type:** Positive
**Priority:** High

**Objective:** `ProductUpdateRequest` fields are all optional and
independently `None`-gated in the service - sending only `price` must leave
`name` and every other field untouched.

**Preconditions:**
- A throwaway product; a valid `If-Match` (its current ETag).

**Expected Result:**
- Response status is 200.
- The updated field changed; every other field equals its pre-update value.

### PROD-017 — Updating an unknown product ID returns 404

**Endpoint:** PUT /api/v1/products/{product_id}
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 404.
- `error.code` is `PRODUCT_NOT_FOUND`.

### PROD-018 — Replacing category_ids replaces the previous set, not adds to it

**Endpoint:** PUT /api/v1/products/{product_id}
**Type:** Positive / Edge case
**Priority:** Medium

**Objective:** Mirrors ADMIN-007's `roles` semantics - `product_categories`
is cleared and rebuilt from `category_ids`, not merged.

**Preconditions:**
- A throwaway product with one category already attached; a second,
  different category to replace it with.

**Expected Result:**
- Response status is 200.
- `categories` equals exactly the new set sent, not the union of old and new.

---

## Delete & Restore

### PROD-019 — Soft-deleting a product removes it from the default listing and get

**Endpoint:** DELETE /api/v1/products/{product_id}
**Type:** Positive / State change
**Priority:** High

**Preconditions:**
- A throwaway product; a valid `If-Match`.

**Expected Result:**
- Response status is 204.
- A subsequent public `GET /products/{id}` returns 404.
- The product's ID is absent from an unfiltered `GET /products`.

### PROD-020 — Restoring a soft-deleted product succeeds and stays inactive

**Endpoint:** POST /api/v1/products/{product_id}/restore
**Type:** Positive
**Priority:** Medium

**Objective:** `apply_restore` only clears `deleted_at` - the product does
not automatically reactivate, so restoring alone does not make it buyable
again.

**Preconditions:**
- A throwaway product, soft-deleted.

**Expected Result:**
- Response status is 200.
- `deleted_at` is `null`.
- `is_active` is unchanged (still `false`, deletion's side effect).

### PROD-021 — Restoring a product that is not deleted returns 404

**Endpoint:** POST /api/v1/products/{product_id}/restore
**Type:** Negative
**Priority:** Low

**Objective:** Distinct from PROD-009 - the product exists and is not
deleted, so "not deleted" is folded into the same `PRODUCT_NOT_FOUND` as
"does not exist" rather than its own code.

**Expected Result:**
- Response status is 404.
- `error.code` is `PRODUCT_NOT_FOUND`.
