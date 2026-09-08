# Inventory API — Test Scenarios

Source of truth: `GET /openapi.json` (paths under `/api/v1/inventory`,
OpenAPI tag `inventory`) cross-checked against
`backend/app/services/inventory_service.py`,
`backend/app/repositories/inventory_repository.py`,
`backend/app/api/routes/inventory.py`, and `backend/app/models/inventory.py`
in the RiveAr App repository.

Every inventory record is created automatically alongside its product
(`product_service.create_product`, `stock=0`, `reorder_threshold=15`) or by
the test factory (`factory("product", stock=...)`, same threshold via
`DEFAULT_REORDER_THRESHOLD`) - there is no standalone factory entity for
`inventory`, and no create/delete endpoint in this API; a record's lifetime
matches its product's.

`InventoryTransactionType` has six values (`PURCHASE`, `RESERVATION`,
`RELEASE`, `SALE`, `ADJUSTMENT`, `RETURN`), but only `ADJUSTMENT` is
reachable through this domain's own endpoint - the other five are written by
the Orders flow (`order_service.py`), out of scope here and deferred to the
orders scenario set.

Endpoints in scope:

- `GET   /inventory`
- `GET   /inventory/{inventory_id}`
- `PATCH /inventory/{inventory_id}`
- `GET   /inventory/{inventory_id}/transactions`

Unlike products, **every** endpoint here - including the `GET`s - requires
`inventory:manage` (`require_permission` on all four routes; there is no
public read path). Covered once, see INV-018.

---

## Listing

### INV-001 — Listing inventory returns paginated results

**Endpoint:** GET /api/v1/inventory
**Type:** Positive
**Priority:** High

**Expected Result:**
- Response status is 200.
- Response has `items` and `pagination` (page, page_size, total, total_pages).

### INV-002 — Filtering by status returns only matching records

**Endpoint:** GET /api/v1/inventory?status=...
**Type:** Positive / Filtering
**Priority:** Medium

**Objective:** Proves the filter mechanism itself, not any particular
status value - a fresh throwaway record's own (whatever it turns out to be)
status is enough; the boundary computation that decides *which* status a
given stock ends up with is INV-012's concern, not this one.

**Preconditions:**
- A throwaway product via the factory.

**Expected Result:**
- Response status is 200.
- Filtering by the record's own `status` returns exactly that record.

### INV-003 — Searching by product name or SKU returns the matching record

**Endpoint:** GET /api/v1/inventory?search=...
**Type:** Positive / Filtering
**Priority:** Medium

**Objective:** `search` matches `Product.name` OR `Product.sku` via a join,
not any field on `Inventory` itself.

**Preconditions:**
- A throwaway product via the factory with a distinctive, unique `name`.

**Expected Result:**
- Response status is 200.
- Searching by the product's `name` returns its inventory record;
  searching by its `sku` also returns it.

### INV-004 — An invalid sort_by returns 422 with the allowed values in the message

**Endpoint:** GET /api/v1/inventory?sort_by=...
**Type:** Validation
**Priority:** Low

**Objective:** Same `resolve_sort` mechanism as PROD-004 - allowed columns
land in `error.message` prose, not `error.details`. Same known issue,
see `BUGS.md` OBS-003.

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.
- `error.message`'s "Allowed values" list names exactly the three real
  sortable columns (`available_stock`, `created_at`, `stock`) - not just a
  substring match, which `available_stock` containing `stock` would let
  pass even if `stock` itself were missing.

---

## Get by ID

### INV-005 — Getting a known inventory record by ID succeeds

**Endpoint:** GET /api/v1/inventory/{inventory_id}
**Type:** Positive
**Priority:** High

**Expected Result:**
- Response status is 200.
- Response equals the record already seen via `GET /inventory` - both
  endpoints build their response through the same `to_response()`, so this
  is a stronger check than any hand-picked subset of fields.

### INV-006 — Getting an unknown inventory ID returns 404

**Endpoint:** GET /api/v1/inventory/{inventory_id}
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 404.
- `error.code` is `INVENTORY_NOT_FOUND`.

---

## Adjust stock

### INV-007 — A positive stock_delta increases stock

**Endpoint:** PATCH /api/v1/inventory/{inventory_id}
**Type:** Positive
**Priority:** High

**Preconditions:**
- A throwaway product via the factory - its actual `stock` (whatever the
  factory's default is) is read back from the record rather than assumed.

**Expected Result:**
- Response status is 200.
- `stock` equals the original value plus `stock_delta`.
- `available_stock` (`stock - reserved_stock`) reflects the new stock.

### INV-008 — A negative stock_delta decreases stock

**Endpoint:** PATCH /api/v1/inventory/{inventory_id}
**Type:** Positive
**Priority:** Medium

**Preconditions:**
- A throwaway product via the factory with `stock` comfortably above 0.

**Expected Result:**
- Response status is 200.
- `stock` equals the original value plus `stock_delta` (negative).

### INV-009 — An adjustment that would take stock negative is rejected

**Endpoint:** PATCH /api/v1/inventory/{inventory_id}
**Type:** Negative / Business rule
**Priority:** High

**Objective:** `adjust_stock` rejects `stock + stock_delta < 0` before
writing anything.

**Preconditions:**
- A throwaway product via the factory - `stock_delta` is computed as
  `-(stock + 1)`, always exactly one past whatever the actual stock is, so
  no specific starting value needs to be assumed.

**Expected Result:**
- Response status is 409.
- `error.code` is `INSUFFICIENT_STOCK`.
- A follow-up GET shows `stock` unchanged - the rejected request wrote
  nothing (no transaction, no stock change).

### INV-010 — An adjustment that would leave stock below reserved_stock is rejected

**Endpoint:** PATCH /api/v1/inventory/{inventory_id}
**Type:** Negative / Business rule
**Priority:** Medium

**Blocker:** No API-only way to produce this precondition exists yet.
`adjust_stock` has two distinct 409 branches - `new_stock < 0` and
`new_stock < reserved_stock` - but every factory-created (or product-created)
inventory record starts with `reserved_stock=0`, and nothing in the current
API surface raises it above 0. `reserved_stock` only moves through the
Orders flow (`order_service.py`, `RESERVATION`/`RELEASE`/`SALE`
transactions), which is out of scope until the orders domain is covered.
Until then this branch is indistinguishable from INV-009 through this API -
revisit once orders exists.

### INV-011 — Adjusting stock records a transaction with the given reason

**Endpoint:** PATCH /api/v1/inventory/{inventory_id}
**Type:** Positive / Side effect
**Priority:** High

**Objective:** Every successful adjustment writes an `InventoryTransaction`
(`type=ADJUSTMENT`) alongside the stock change, visible through
GET .../transactions (INV-015).

**Preconditions:**
- A throwaway product via the factory.

**Expected Result:**
- Response status is 200.
- A subsequent `GET .../transactions` includes an entry with
  `quantity_change` equal to the `stock_delta` sent, `stock_after` equal to
  the resulting `stock`, and `note` equal to the `reason` sent.

### INV-012 — Stock crossing the reorder threshold recomputes status through all three states

**Endpoint:** PATCH /api/v1/inventory/{inventory_id}
**Type:** Positive / Boundary / State transition
**Priority:** High

**Objective:** `status_for()`: `available <= 0` -> `OUT_OF_STOCK`,
`available <= reorder_threshold` -> `LOW_STOCK`, else `IN_STOCK`.
`reserved_stock` is always 0 here (see INV-010), so `available == stock`.
The factory-created threshold is 15 (`DEFAULT_REORDER_THRESHOLD`).

**Preconditions:**
- A throwaway product via the factory with `stock=0` (starts `OUT_OF_STOCK`,
  matching product creation's own computation).

**Expected Result:**
- Adjusting to `stock=15` (`stock_delta=15`) returns `status=LOW_STOCK`
  (exactly at the threshold is still low, not in-stock).
- A further adjustment to `stock=16` (`stock_delta=1`) returns
  `status=IN_STOCK`.

### INV-013 — Adjusting an unknown inventory ID returns 404

**Endpoint:** PATCH /api/v1/inventory/{inventory_id}
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 404.
- `error.code` is `INVENTORY_NOT_FOUND`.

### INV-014 — Concurrent stock adjustments can lose writes

**Endpoint:** PATCH /api/v1/inventory/{inventory_id}
**Type:** Negative / Concurrency defect
**Priority:** High

**Objective:** Reproduces `BUG-003` (see `BUGS.md`). Unlike
`order_service.py`, which reads the row via
`inventory_repository.get_for_product(..., lock=True)` before mutating
stock, `adjust_stock` reads it via plain `get_by_id` - no
`SELECT ... FOR UPDATE`. Concurrent adjustments can therefore both read the
same starting `stock`, both compute their own new value from it, and the
second write silently overwrites the first - a classic lost update. Verified
empirically: 20 concurrent `stock_delta=1` requests against a fresh record
consistently land 4-17 updates short of the expected total, every request
individually returning 200 and every one of the 20 recording its own
`InventoryTransaction` row - the transaction log is complete and correct,
only the `stock` column itself loses writes.

**Preconditions:**
- A throwaway product via the factory - its actual `stock` is read back
  from the record, not assumed.

**Expected Result (correct behaviour, currently failing against the SUT):**
- After N concurrent requests each with `stock_delta=1`, the final `stock`
  equals the original value plus N, and the transaction history
  (INV-015) contains exactly N entries.
- **Actual (current SUT behaviour):** all N requests return 200 and all N
  transactions are recorded, but the final `stock` is less than
  original + N - some concurrent writes are lost.

---

## Transaction history

### INV-015 — Transaction history lists entries in reverse-chronological order

**Endpoint:** GET /api/v1/inventory/{inventory_id}/transactions
**Type:** Positive
**Priority:** Medium

**Preconditions:**
- A throwaway product via the factory, adjusted twice with different
  `stock_delta` values.

**Expected Result:**
- Response status is 200.
- Response has `items` and `pagination`.
- The two adjustments both appear, most recent first (`created_at` desc).

### INV-016 — Transaction history for an unknown inventory ID returns 404

**Endpoint:** GET /api/v1/inventory/{inventory_id}/transactions
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 404.
- `error.code` is `INVENTORY_NOT_FOUND`.

### INV-017 — Transaction history is scoped to its own inventory record

**Endpoint:** GET /api/v1/inventory/{inventory_id}/transactions
**Type:** Negative / Isolation
**Priority:** Medium

**Objective:** A missing or wrong `WHERE inventory_id = ...` in the
repository query would leak every inventory record's transactions into
every other record's history - worth confirming directly rather than
assuming the filter is there.

**Preconditions:**
- Two throwaway products, each adjusted once with a distinctive
  `stock_delta`.

**Expected Result:**
- The first record's transaction history contains its own adjustment only,
  not the second record's.

---

## Permission boundary

### INV-018 — Inventory endpoints require inventory:manage

**Endpoint:** GET /api/v1/inventory
**Type:** Negative / Security
**Priority:** High

**Objective:** All four endpoints share the exact same
`require_permission("inventory:manage")` dependency (`require_inventory_manager`
in `inventory.py`) - one representative check (the plain `GET`, cheapest to
set up) is enough to prove the boundary; not re-covered per endpoint.

**Expected Result:**
- No/invalid token -> 401 (`TOKEN_MISSING`/`TOKEN_INVALID`).
- Authenticated without `inventory:manage` (e.g. a plain customer) -> 403
  `INSUFFICIENT_PERMISSIONS`.
