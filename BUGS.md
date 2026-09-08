# Defect log — RiveAr

Defects and behavioural observations found while building the automated test
suite against RiveAr. Kept in the TAF repository rather than the application's,
because this is a QA artefact: it records what testing found, what evidence
supports it, and which automated test now guards each fix.

**Conventions**

- `BUG-*` — the application does something it should not. Reproducible.
- `OBS-*` — behaviour that is defensible but surprising, or an inconsistency
  worth a decision. Recorded so it is a choice rather than an accident.

| Severity | Meaning |
|---|---|
| High | Wrong information reaching users, data integrity, or a security boundary |
| Medium | A feature is unreachable or unusable through its intended path |
| Low | Cosmetic, or an inconsistency with no user-visible impact |

## Summary

| ID | Severity | Status | Area | Summary | Test |
|---|---|---|---|---|---|
| [BUG-001](#bug-001) | High | Fixed | API | Product page served stale stock after an order, via a 304 | PROD-15 |
| [BUG-002](#bug-002) | Medium | Open | UI | Staff have no navigation to the admin dashboard | — |
| [BUG-003](#bug-003) | High | Open | API | Concurrent stock adjustments lose writes - no row lock | INV-014 |
| [BUG-004](#bug-004) | High | Open | API | Concurrent order creation loses stock reservations, despite a row lock | ORD-016 |
| [OBS-001](#obs-001) | Low | Open | API/UI | Default catalogue listing includes unbuyable products | PROD-002 |
| [OBS-002](#obs-002) | Low | Open | API | Zero decimals serialise as `"0"`, non-zero as `"20.00"` | PROMO-03 |
| [OBS-003](#obs-003) | Low | Open | API | Some validation errors put machine-readable data in prose | PROD-004 |
| [OBS-004](#obs-004) | Low | Open | API | `/test/cleanup` on a "customer" leaves the User account behind | — |

---

## BUG-001

**Product detail endpoint answers 304 after stock has changed, so the
storefront keeps displaying the pre-order availability.**

| | |
|---|---|
| Severity | High |
| Status | **Fixed** 2026-08-20 |
| Area | Backend — `GET /api/v1/products/{id}` |
| Found | Exploratory testing while checking inventory reservation behaviour |
| Regression test | `PROD-15` in `tests/test_products.py` |

### What happens

The endpoint issues an `ETag` derived from `products.version` and answers
`304 Not Modified` when a client revalidates with a matching `If-None-Match`.

But the response body also carries `available_stock` and `inventory_status`,
which come from the **`inventory` table**. Placing an order changes
`inventory.reserved_stock` and never touches `products.version`, so the
validator does not cover everything the representation contains.

The server therefore tells any caching client "nothing changed" about a body
whose stock figures have in fact moved. The frontend calls `fetch()` with the
browser's default caching (`frontend/src/api/client.ts`), so the browser
revalidates, receives the 304, and re-serves the stale cached body.

### Steps to reproduce

1. As a customer, open a product's detail page and note the `N available`
2. Place an order for that product, quantity `Q`
3. Return to the product page and reload

**Expected:** `N - Q` available.
**Actual:** still `N`. The number never changes, however long you wait.

### Evidence

The database was correct throughout — inventory transaction log for `AUDI-002`
after order `ORD-000247` (3 units, later shipped):

```
08:21  RESERVATION  +3   Reserved for order ORD-000247
08:27  SALE         -3   stock_after=61   Sold: order ORD-000247 shipped
```

Resulting row: `stock=61 reserved=0 available=61` — down from 64, exactly as
designed.

An unconditional request returned the correct figure; a conditional one did
not return it at all:

```
GET /api/v1/products/{id}                       -> 200, available_stock = 61, ETag: "2"
GET /api/v1/products/{id}  If-None-Match: "2"   -> 304  (no body)
```

`products.version` was `2` before and after the order, because ordering writes
to `inventory`, not to `products`.

### Why neither an API nor a UI test would have caught it

- An API test issues a fresh `GET` with no `If-None-Match`, gets 61, passes
- A UI test on the catalogue page passes too — the listing endpoint sets no
  ETag, so it is unaffected
- Only a test that is deliberately conscious of HTTP cache validation fails

That gap is why `PROD-15` exists.

### Root cause

An ETag must be a validator for the **entire representation**. This one
validated a single row of one table while the representation joined two.

### Fix

`backend/app/api/routes/products.py` — removed the 304 short-circuit from
`get_product`, keeping `set_etag`:

```python
-    if is_not_modified(request, product.version):
-        raise HTTPException(status_code=http_status.HTTP_304_NOT_MODIFIED)
     set_etag(response, product.version)
```

The ETag is still issued and still correct for its other purpose: `PUT` and
`DELETE` require it back via `If-Match`, and there `products.version` is
exactly the right validator, because those operations only guard the product
row. Only the read-side caching optimisation was unsound.

The alternative — widening the ETag to cover inventory as well, e.g.
`f'"{product.version}-{inventory.updated_at.timestamp()}"'` — preserves the
optimisation but complicates `require_if_match`, which would then have to
accept a compound tag for writes that only concern the product row. On a
public catalogue endpoint the saved bandwidth does not justify that.

### Verification

The regression test was confirmed to detect the defect, not merely to pass:

| Application state | `PROD-15` |
|---|---|
| Before fix | **fails** — `Expected status 200, got 304` |
| After fix | passes |

### Follow-up

`is_not_modified()` in `backend/app/core/concurrency.py` now has no callers.
It is a sound general-purpose helper, so it was left in place rather than
widening this fix, but it is dead code today.

---

## BUG-002

**Staff accounts have no way to reach the admin dashboard from the interface.**

| | |
|---|---|
| Severity | Medium |
| Status | Open |
| Area | Frontend — `components/layout/Navbar.tsx`, `pages/LoginPage.tsx` |
| Found | Exploratory testing — attempting to sign in as an administrator |
| Regression test | Planned for increment 5 (UI layer) |

### What happens

The dashboard exists and works at `/dashboard`, gated correctly by
`RoleRoute roles={STAFF_ROLES}`. Nothing in the UI links to it.

The storefront navigation is a hardcoded pair:

```js
const NAV_LINKS = [
  { label: "Home", to: "/" },
  { label: "Products", to: "/products" },
];
```

The account menu offers "Order history" only when `isCustomer`, plus "Log
out". An administrator holds no `CUSTOMER` role, so they see **fewer** options
than a shopper. Login always redirects to `/` or the page the user came from —
there is no branch on role.

### Steps to reproduce

1. Sign in as `admin@rivear.local`
2. Look anywhere in the interface for a link to the dashboard

**Expected:** a visible entry point for staff.
**Actual:** none. The dashboard is reachable only by typing `/dashboard`.

### Evidence

Read the accessibility tree while signed in as the administrator; the account
menu contained exactly two items — the disabled name/email row and "Log out".
Navigating directly to `/dashboard` rendered the full dashboard, confirming
routing and permissions are fine and only the entry point is missing.

### Suggested fix

Add a dashboard entry to the account menu (and the mobile drawer) behind the
`isStaff` flag that `AuthContext` already exposes. Optionally redirect staff
to `/dashboard` after login when no explicit return path was requested.

Not applied — outside the scope of the change that was authorised.

---

## BUG-003

**Concurrent `PATCH /inventory/{id}` requests can silently lose stock
adjustments - no row-level locking on the read.**

| | |
|---|---|
| Severity | High |
| Status | Open |
| Area | Backend — `inventory_service.adjust_stock` |
| Found | Designing inventory API test scenarios - probing concurrent stock
adjustments before writing INV-014 |
| Regression test | `INV-014` in `tests/test_inventory.py` (currently
expected to fail against the live SUT) |

### What happens

`adjust_stock` reads the inventory row via
`inventory_repository.get_by_id()`, computes `new_stock = inventory.stock +
stock_delta` in Python, and writes it back - a classic read-modify-write
with no locking in between. Two concurrent requests against the same record
can both read the same starting `stock`, both compute their own new value
from it, and whichever commits second overwrites the first's write instead
of building on it.

The order-checkout path already knows this pattern needs a lock -
`order_service.py` reads the row via
`inventory_repository.get_for_product(db, product_id, lock=True)`
(`SELECT ... FOR UPDATE`) specifically so concurrent checkouts of the same
product serialize (the function's own docstring explains why). `adjust_stock`
calls a different repository function, `get_by_id`, which has no `lock`
parameter at all - the pattern was applied correctly in one place and missed
in the other.

### Steps to reproduce

1. Create a product with a known `stock` (e.g. 1000)
2. Fire 20 concurrent `PATCH /inventory/{id}` requests, each
   `{"stock_delta": 1}`
3. Once all 20 have returned `200`, `GET` the record's final `stock` and its
   transaction history

**Expected:** `stock` is `1020`; 20 transactions recorded.
**Actual:** `stock` lands somewhere between 1003 and 1005 depending on the
run - every one of the 20 transactions is still recorded (the audit trail is
complete and correct), but 15-17 of the actual stock increments never
persisted.

### Evidence

Live against the running SUT, four consecutive trials of the same 20x
`stock_delta=1` probe from a fresh `stock=1000` record:

```
trial 1: before=1000 after=1004 expected=1020 transactions_recorded=20
trial 2: before=1000 after=1005 expected=1020 transactions_recorded=20
trial 3: before=1000 after=1004 expected=1020 transactions_recorded=20
trial 4: before=1000 after=1005 expected=1020 transactions_recorded=20
```

Every trial: 20/20 requests returned `200`, 20/20 transactions were recorded
with correct per-request `quantity_change`/`stock_after` values, yet the
`stock` column itself only reflects 3-5 of the 20 increments. This is not a
rejected-request or validation issue - every write was individually accepted
and individually logged; they overwrote each other.

A single run with no concurrency (20 sequential requests, one at a time)
produces the correct `1020` every time - the defect only manifests under
genuine concurrent access, which is exactly what row locking exists to
guard against.

### Root cause

`inventory_service.adjust_stock` mutates `inventory.stock` after reading it
through a repository call with no `SELECT ... FOR UPDATE`, so two
overlapping transactions can both hold the pre-adjustment value in memory
at once. Contrast with the correctly-locked read one call away in
`order_service.py`.

### Suggested fix

Have `adjust_stock` acquire the row lock before mutating, either via a new
`lock=True`-capable lookup mirroring `get_for_product`, or by adding a
`lock` parameter to `get_by_id` itself and passing `lock=True` from
`adjust_stock`. Not applied - outside the scope of the change that was
authorised, and this file records testing findings rather than making them.

---

## BUG-004

**Concurrent order creation for the same product loses stock
reservations - even though the read is explicitly row-locked.**

| | |
|---|---|
| Severity | High |
| Status | Open |
| Area | Backend — `order_service._resolve_line_items` |
| Found | Designing orders API test scenarios - probing concurrent order
creation before writing ORD-016, after finding the superficially similar
`BUG-003` |
| Regression test | `ORD-016` in `tests/test_orders.py` (currently
expected to fail against the live SUT) |

### What happens

`_resolve_line_items` reads each product's inventory row via
`inventory_repository.get_for_product(db, product_id, lock=True)` - a real
`SELECT ... FOR UPDATE`, exactly the pattern that's *missing* in `BUG-003`.
By the standard Postgres locking model, a second transaction's
`SELECT ... FOR UPDATE` on a row already locked by an uncommitted first
transaction should block, then - once the first commits - re-read the
now-current row and lock it in turn. That should make concurrent
reservations serialize correctly. It does not: concurrent order creation
for the same product still loses `reserved_stock` increments, with the
same signature as `BUG-003` (every request succeeds, every
`InventoryTransaction` is individually recorded, only the `reserved_stock`
column itself ends up wrong).

This makes it a different, and arguably more serious, defect than
`BUG-003`: that one is missing a lock outright, with a straightforward
fix. This one has the lock in place and still loses updates, which points
at something wrong with how the lock, the session, or the transaction
boundary interact - not simply "add `lock=True` here too."

### Steps to reproduce

1. Create a product with ample stock (e.g. 500)
2. Fire 2 (or 10) concurrent `POST /orders`, each ordering 1 unit of that
   product
3. Check the product's `reserved_stock` via `GET /inventory` and its
   transaction count via `GET /inventory/{id}/transactions`

**Expected:** `reserved_stock` equals the number of orders placed (2, or
10); that many `RESERVATION` transactions recorded.
**Actual:** every order returns `201`, every `RESERVATION` transaction is
recorded (2/2, or 10/10), but `reserved_stock` is `1` regardless of how
many concurrent orders were placed.

### Evidence

Live against the running SUT:

```
2 concurrent orders:  both 201, reserved_stock = 1 (expected 2)
10 concurrent orders: all 201, 10/10 RESERVATION transactions, reserved_stock = 1 (expected 10)
```

The 10-concurrent case was run three times; every trial landed on exactly
`reserved_stock = 1`. That it is consistently exactly `1`, not a variable
shortfall the way `BUG-003`'s losses ranged 3-5 out of 20, is itself a
clue: it reads as every concurrent transaction computing its update from
the *same* pre-existing value (as if none of them ever actually blocked
waiting for another's lock), with whichever commits last simply
overwriting the rest - rather than a partial, timing-dependent loss.

A sequential (non-concurrent) run of the same N order creations produces
the correct `reserved_stock = N` every time.

### Root cause

Not established. The code takes the correct row lock
(`get_for_product(..., lock=True)`), which under standard Postgres
`READ COMMITTED` semantics should prevent exactly this. Candidates worth
investigating, none confirmed: whether `with_for_update()` is emitting the
`FOR UPDATE` clause SQLAlchemy expects it to in this call path, the
engine/session's actual isolation level and transaction boundaries
(`app/db/session.py` - `create_engine(..., pool_pre_ping=True)`, plain
`sessionmaker(autocommit=False, autoflush=False)`), and whether something
about `_resolve_line_items` running inside `_build_order` (called from
`create_order`, which commits once at the very end) defers the actual
lock-acquiring `SELECT` differently than a direct call would.

### Suggested fix

Requires further investigation into why the existing lock isn't
serializing these transactions before attempting a fix - not applied here.
This file records testing findings rather than making them.

---

## OBS-001

**The default product listing includes products that cannot be bought.**

| | |
|---|---|
| Severity | Low |
| Status | Open — decision needed |
| Area | Backend `GET /api/v1/products` + storefront |
| Covered by | `PROD-002` (documents current behaviour) |

`GET /products` applies no availability filter unless the caller passes
`?status=active`. The storefront sends that parameter only when the shopper
picks the availability filter themselves, so by default the catalogue lists
inactive products.

Ordering one, or adding it to a cart, is correctly refused with
`PRODUCT_INACTIVE` — so the shop advertises items it will then decline to
sell. The API behaves as specified (the filter is opt-in); the question is
whether the storefront should be opting in by default.

Note the parameter is exposed as `status`, while the handler argument is named
`status_filter`. Passing `?status_filter=active` is silently ignored, since
FastAPI discards unknown query parameters — an easy trap when writing tests.

---

## OBS-002

**Decimal fields serialise inconsistently depending on their value.**

| | |
|---|---|
| Severity | Low |
| Status | Open |
| Area | Backend — Decimal serialisation |
| Covered by | `PROMO-03` (compares numerically) |

`POST /promotions/validate` returns `discount_amount` as `"20.00"` when a
discount applies, but `"0"` when none does — the same field, two different
formats:

```json
{"valid": true,  "discount_amount": "20.00"}
{"valid": false, "discount_amount": "0"}
```

No user-visible impact, and any client parsing numerically is fine. Recorded
because string-comparing such a field is a trap: the tests here parse the
value rather than matching its text.

---

## OBS-003

**Some validation errors put machine-readable data in the message instead of
`details`.**

| | |
|---|---|
| Severity | Low |
| Status | Open |
| Area | Backend — validation errors |
| Covered by | `PROD-004` (asserts the status and code only) |

An invalid `sort_by` returns the permitted values as prose, with `details`
empty:

```json
{"error": {"code": "VALIDATION_ERROR",
           "message": "Invalid sort_by 'sku'. Allowed values: created_at, name, price, rating.",
           "details": {}}}
```

The order state machine handles the equivalent case the other way, and better:

```json
{"error": {"code": "INVALID_STATUS_TRANSITION",
           "details": {"from": "PENDING", "to": "SHIPPED",
                       "allowed": ["CANCELLED", "CONFIRMED"]}}}
```

A client that wants to react to the first case has to parse English. The
second is directly usable. Worth aligning, since the structured envelope
exists precisely so clients never have to read messages.

---

## OBS-004

**`DELETE /test/cleanup` for a factory-created customer deletes the
`Customer` profile but leaves the underlying `User` account behind.**

| | |
|---|---|
| Severity | Low |
| Status | Open |
| Area | Backend — `test_support_service.cleanup_run` |
| Found | Live demo while explaining the `factory`/`run_id` fixtures |

### What happens

`POST /test/factory/customer` creates two rows: a `User` (email, password
hash — what login actually checks) and a `Customer` (the profile linked to
it). The cleanup map only knows about one of them:

```python
_CLEANUP_MODELS = {
    "product": Product,
    "customer": Customer,   # only the profile, never the User
    "category": Category,
    "promotion": Promotion,
}
```

`DELETE /test/cleanup?run_id=...` reports `"deleted": 1` and genuinely does
delete the `Customer` row. The `User` row is untouched, so the account is
**still fully able to log in** afterward — cleanup looks complete but is not.

### Steps to reproduce

1. `POST /test/factory/customer` with a `run_id`
2. `DELETE /test/cleanup?run_id=...` → reports `deleted: 1`
3. `POST /auth/login` with that same account's email/password

**Expected:** login fails — the account was cleaned up.
**Actual:** login succeeds (`200`), same as before cleanup.

### Impact

Low severity: these are disposable, fictional dev-only accounts, and the
leak is only ever a `User` row with no `Customer` profile attached — not a
security issue, not user-facing. But it means a long-running or frequently
re-run test suite accumulates orphaned `User` rows forever, since there is no
public endpoint that can remove them. `POST /test/reset` clears everything
including these, so the leak is bounded by how often the database gets reset,
not unbounded in practice.

### Suggested fix

Add `User` to the customer cleanup path in `cleanup_run` — delete the
`Customer` row's owning `User` too when the factory created both together.
Not applied — outside the scope of the change that was authorised, and
this file records testing findings rather than making them.
