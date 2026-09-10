# Orders API — Test Scenarios

Source of truth: `GET /openapi.json` (paths under `/api/v1/orders`, OpenAPI
tag `orders`) cross-checked against `backend/app/services/order_service.py`,
`backend/app/services/payment_service.py`,
`backend/app/services/idempotency_service.py`,
`backend/app/repositories/order_repository.py`, and
`backend/app/api/routes/orders.py` in the RiveAr App repository.

`GET /orders/{id}/returns/eligibility` and `POST /orders/{id}/returns` carry
a separate OpenAPI tag (`returns`) and their own domain logic - deliberately
out of scope here, for their own future scenario set.

Endpoints in scope:

- `GET   /orders`
- `POST  /orders`
- `POST  /orders/checkout`
- `GET   /orders/{order_id}`
- `PATCH /orders/{order_id}/status`
- `GET   /orders/{order_id}/status-history`
- `POST  /orders/{order_id}/payment/process`

**Authorization model** (three different shapes, not one boundary reused
everywhere):
- `POST /orders`, `POST /orders/checkout` - customer accounts only
  (`require_customer_profile`); a staff account with no `Customer` profile
  gets 403.
- `GET /orders`, `GET /orders/{id}`, `GET .../status-history`,
  `POST .../payment/process` - any authenticated user, but a customer only
  ever sees/acts on their **own** orders; another customer's order is a 404,
  not a 403, so its existence isn't leaked. Staff (`SUPPORT`/`MANAGER`/
  `ADMIN`, role-based via `is_staff()`, not a granular permission string)
  see everything.
- `PATCH .../status` - staff may drive any valid state-machine transition;
  a customer may only cancel their own `PENDING`/`CONFIRMED` order.

Pricing (from `order_service.py`, backed by a settings table): 8% tax on
the subtotal, free shipping at/above a $75 subtotal else a flat $9.99.
Verified live, not assumed.

`POST /orders/{id}/payment/process`'s 404 `PAYMENT_NOT_FOUND` branch is not
covered by a scenario here: every order gets a `Payment` row at creation
time, and there is no way through this API to produce an order with none -
the same kind of API-unreachable branch as `BULK-006` in `products.md`.

---

## Permission boundary

### ORD-001 — Orders endpoints require authentication

**Endpoint:** GET /api/v1/orders
**Type:** Negative / Security
**Priority:** High

**Objective:** One representative check that the plain "must be logged in"
*mechanism* (`get_current_user`) behaves correctly; the customer-vs-staff
distinctions themselves are each covered by their own scenario above
(ORD-006, ORD-011, ORD-025, ORD-032). Does not prove every route is
actually wired to it - see ORD-002 for that.

**Expected Result:**
- Response status is 401.
- `error.code` is `TOKEN_MISSING`.

### ORD-002 — Every order endpoint requires authentication

**Endpoint:** all seven order endpoints
**Type:** Negative / Security
**Priority:** High

**Objective:** Complements ORD-001: a route missing its
`Depends(get_current_user)` entirely is a real, distinct failure mode a
black-box test can only catch by calling that specific route -
parametrized rather than seven near-identical tests.

**Expected Result:**
- Every endpoint, called with no token, returns 401 `TOKEN_MISSING`.

---

## Response schema

### ORD-003 — Order response matches the OrderResponse schema

**Endpoint:** POST /api/v1/orders/{order_id}/payment/process
**Type:** Positive / Contract
**Priority:** Medium

**Objective:** Full-shape validation via `api.models.order.OrderResponse`
(Pydantic), including its nested `items`/`payment`/`shipping_address` -
catches drift in fields no existing scenario asserts on individually.
Attaches a real address and processes payment first so those nested
objects are actually populated (non-null) rather than trivially absent,
the way most other scenarios in this file leave them.

**Expected Result:**
- Response status is 200.
- `OrderResponse.model_validate(response.json())` raises no
  `ValidationError`; `items`, `payment`, and `shipping_address` are all
  non-null/non-empty.

### ORD-004 — Status history response matches the OrderStatusHistoryResponse schema

**Endpoint:** GET /api/v1/orders/{order_id}/status-history
**Type:** Positive / Contract
**Priority:** Medium

**Preconditions:**
- An order cancelled with a `note`, so both a `from_status: null` entry
  (creation) and a `note`-carrying entry exist.

**Expected Result:**
- Response status is 200.
- `OrderStatusHistoryResponse.model_validate(...)` raises no
  `ValidationError` for every returned item.

---

## Listing

### ORD-005 — Listing orders returns paginated results

**Endpoint:** GET /api/v1/orders
**Type:** Positive
**Priority:** High

**Expected Result:**
- Response status is 200.
- Response has `items` and `pagination`.

### ORD-006 — A customer's order list is scoped to their own orders

**Endpoint:** GET /api/v1/orders
**Type:** Negative / Isolation
**Priority:** High

**Objective:** `list_orders` force-sets `customer_id` to the caller's own
when the caller isn't staff, silently overriding anything else - worth
confirming directly rather than trusting the description.

**Preconditions:**
- Two throwaway customers, each with an order.

**Expected Result:**
- The first customer's list contains their own order, not the second
  customer's.

### ORD-007 — Staff can list all orders and filter by customer_id

**Endpoint:** GET /api/v1/orders?customer_id=...
**Type:** Positive
**Priority:** Medium

**Expected Result:**
- Response status is 200.
- Filtering by a specific customer's ID (as staff) returns only that
  customer's orders.

### ORD-008 — An invalid sort_by returns 422 with the allowed values in the message

**Endpoint:** GET /api/v1/orders?sort_by=...
**Type:** Validation
**Priority:** Low

**Objective:** Same `resolve_sort` mechanism as `PROD-007`/`INV-008` - same
known issue, see `BUGS.md` OBS-003.

**Expected Result:**
- Response status is 422.
- `error.message`'s "Allowed values" list names exactly the three real
  sortable columns (`created_at`, `order_number`, `total`).

---

## Create order

### ORD-009 — Creating an order with valid items succeeds

**Endpoint:** POST /api/v1/orders
**Type:** Positive
**Priority:** High

**Objective:** The full happy path in one scenario: pricing, inventory
reservation, and the initial payment/history rows this endpoint is
documented to create.

**Preconditions:**
- A throwaway product with a known price and stock.

**Expected Result:**
- Response status is 201.
- `status` is `PENDING`; `subtotal`/`tax_total`/`shipping_total`/`total`
  match the pricing rules; `items` echoes the product with a price
  snapshot.
- `payment.status` is `PENDING`, `payment.amount` equals `total`.
- The product's `reserved_stock` increases by the ordered quantity
  (confirmed via `GET /inventory`).

### ORD-010 — Free shipping applies at/above the threshold, a flat cost below it

**Endpoint:** POST /api/v1/orders
**Type:** Positive / Boundary
**Priority:** Medium

**Objective:** `shipping_total` is `0` at/above a $75 subtotal, else a flat
$9.99 - verified live: a $20 order carries `shipping_total: "9.99"`; an
$80 order carries `"0.00"`.

**Expected Result:**
- A sub-$75 order's `shipping_total` is `9.99`.
- A $75-or-above order's `shipping_total` is `0.00`.

### ORD-011 — Creating an order without a customer profile returns 403

**Endpoint:** POST /api/v1/orders
**Type:** Negative
**Priority:** High

**Objective:** A staff account (no `Customer` profile) cannot place orders
as itself.

**Expected Result:**
- Response status is 403.
- `error.code` is `INSUFFICIENT_PERMISSIONS`.

### ORD-012 — An empty items list is rejected

**Endpoint:** POST /api/v1/orders
**Type:** Validation
**Priority:** Low

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.

### ORD-013 — Ordering a nonexistent product returns 404

**Endpoint:** POST /api/v1/orders
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 404.
- `error.code` is `PRODUCT_NOT_FOUND`.

### ORD-014 — Ordering an inactive product returns 409

**Endpoint:** POST /api/v1/orders
**Type:** Negative / Business rule
**Priority:** Medium

**Preconditions:**
- A throwaway product created with `is_active=false`.

**Expected Result:**
- Response status is 409.
- `error.code` is `PRODUCT_INACTIVE`.

### ORD-015 — Ordering more than available stock returns 409 with the shortfall

**Endpoint:** POST /api/v1/orders
**Type:** Negative / Business rule
**Priority:** High

**Objective:** `quantity` is capped at 100 by the schema itself - the
requested amount must stay under that cap while still exceeding the
product's actual stock, to reach `INSUFFICIENT_STOCK` rather than a
422 schema violation.

**Preconditions:**
- A throwaway product with a small known `stock` (e.g. 5); request more
  than that but under 100.

**Expected Result:**
- Response status is 409.
- `error.code` is `INSUFFICIENT_STOCK`.
- `error.details` carries `product_id`, `available`, and `requested`.

### ORD-016 — An address not belonging to the customer is rejected

**Endpoint:** POST /api/v1/orders
**Type:** Negative / Security
**Priority:** Medium

**Preconditions:**
- Two throwaway customers; the first creates an address via
  `POST /me/addresses`; the second attempts to order using that address's
  ID as `shipping_address_id`.

**Expected Result:**
- Response status is 422.
- `error.code` is `VALIDATION_ERROR`.

### ORD-017 — A valid promotion code applies a discount

**Endpoint:** POST /api/v1/orders
**Type:** Positive
**Priority:** Medium

**Objective:** Confirms the integration point only (promo code accepted,
`discount_total` reflected in the order) - promotion validation's own edge
cases belong to a future promotions scenario set, not repeated here.

**Preconditions:**
- A throwaway product; a valid, active promotion code from the seed data.

**Expected Result:**
- Response status is 201.
- `discount_total` is greater than `0`; `promotion_id` is set.
- A `promotion_usage` row records the order and its discount, and the
  promotion's `usage_count` goes up by one. Neither is exposed by any
  endpoint, so this is checked in the database.

### ORD-018 — Retrying a create request with the same Idempotency-Key replays the original order

**Endpoint:** POST /api/v1/orders
**Type:** Positive / Idempotency
**Priority:** High

**Objective:** A network-retried "create order" must not create a second
order.

**Preconditions:**
- A throwaway product; two identical requests sent with the same
  `Idempotency-Key` header.

**Expected Result:**
- Both responses are 201 with the identical `order_number`/`id`.
- The second response carries the `Idempotent-Replay: true` header.
- Only one order actually exists (confirmed via `GET /orders`).
- Exactly one inventory transaction exists for it - one order is not the
  same as one reservation, and a replay that re-ran the stock side
  effects would still leave a single order behind.

### ORD-019 — Reusing an Idempotency-Key with a different request body is rejected

**Endpoint:** POST /api/v1/orders
**Type:** Negative / Idempotency
**Priority:** Medium

**Expected Result:**
- Response status is 422.
- `error.code` is `IDEMPOTENCY_KEY_REUSED`.
- `error.details` names the `key` and the `original_endpoint`.

### ORD-020 — Concurrent order creation for the same product loses stock reservations

**Endpoint:** POST /api/v1/orders
**Type:** Negative / Concurrency defect
**Priority:** High

**Objective:** Reproduces `BUG-004` (see `BUGS.md`). `_resolve_line_items`
reads the inventory row via `inventory_repository.get_for_product(...,
lock=True)` - a real `SELECT ... FOR UPDATE`, unlike `BUG-003`'s
completely unlocked read - yet concurrent order creation for the same
product still loses reservations. Verified empirically: even just 2
concurrent single-item orders for the same product, both returning 201,
leave `reserved_stock` at 1 instead of 2; at 10 concurrent orders,
`reserved_stock` lands at 1 instead of 10, every trial (3/3), despite all
10 `RESERVATION` transactions being individually recorded correctly. The
presence of an explicit row lock makes this a different (and more
concerning) defect than `BUG-003`, not the same one - see `BUGS.md` for
what was and wasn't established about the cause.

**Preconditions:**
- A throwaway product with ample stock (e.g. 500).

**Expected Result (correct behaviour, currently failing against the SUT):**
- After N concurrent single-item orders, `reserved_stock` equals N.
- **Actual (current SUT behaviour):** all N requests return 201, all N
  `RESERVATION` transactions are recorded, but `reserved_stock` is far
  short of N (observed: exactly 1, regardless of N).

---

## Checkout

### ORD-021 — Checking out a non-empty cart creates an order and clears the cart

**Endpoint:** POST /api/v1/orders/checkout
**Type:** Positive
**Priority:** High

**Preconditions:**
- A throwaway product added to the customer's cart (`POST /cart/items` -
  cart domain, out of scope otherwise; only used here as a precondition).

**Expected Result:**
- Response status is 201; the order's `items` match what was in the cart.
- A subsequent `GET /cart` shows an empty cart.

### ORD-022 — Checking out an empty cart returns 409

**Endpoint:** POST /api/v1/orders/checkout
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 409.
- `error.code` is `CART_EMPTY`.

### ORD-023 — A failed checkout leaves the cart untouched

**Endpoint:** POST /api/v1/orders/checkout
**Type:** Negative / State change
**Priority:** High

**Objective:** Checkout and clearing the cart happen in one transaction -
confirms a mid-workflow failure (insufficient stock) doesn't silently
clear the cart anyway.

**Preconditions:**
- The customer's cart holds more of a product than is currently in stock.

**Expected Result:**
- Response status is 409.
- A subsequent `GET /cart` still shows the same item(s).

---

## Get order

### ORD-024 — Getting your own order succeeds

**Endpoint:** GET /api/v1/orders/{order_id}
**Type:** Positive
**Priority:** High

**Expected Result:**
- Response status is 200; the response matches the order just created.

### ORD-025 — Getting another customer's order returns 404, not 403

**Endpoint:** GET /api/v1/orders/{order_id}
**Type:** Negative / Security
**Priority:** High

**Objective:** `ensure_can_view_order` deliberately answers 404 rather than
403 for an order that exists but isn't the caller's, so a customer can't
use the status code alone to enumerate which order IDs are real.

**Expected Result:**
- Response status is 404.
- `error.code` is `ORDER_NOT_FOUND`.

### ORD-026 — Staff can get any order

**Endpoint:** GET /api/v1/orders/{order_id}
**Type:** Positive
**Priority:** Medium

**Expected Result:**
- Response status is 200 for a staff caller viewing a customer's order.

### ORD-027 — Getting an unknown order ID returns 404

**Endpoint:** GET /api/v1/orders/{order_id}
**Type:** Negative
**Priority:** Medium

**Expected Result:**
- Response status is 404.
- `error.code` is `ORDER_NOT_FOUND`.

---

## Order status

### ORD-028 — Staff can walk an order through the full happy-path state machine

**Endpoint:** PATCH /api/v1/orders/{order_id}/status
**Type:** Positive
**Priority:** High

**Objective:** `PENDING -> CONFIRMED -> PROCESSING -> SHIPPED -> DELIVERED`
in one scenario - a single coherent proof of the whole chain rather than
four disconnected transition tests.

**Expected Result:**
- Each transition returns 200 with `status` reflecting the new value.
- The final state is `DELIVERED`.

### ORD-029 — An invalid transition is rejected with machine-readable details

**Endpoint:** PATCH /api/v1/orders/{order_id}/status
**Type:** Negative / Business rule
**Priority:** High

**Objective:** Unlike `PROD-007`/OBS-003's prose-only validation message,
this endpoint's error is the good example already referenced there:
structured `details`, not English the caller has to parse.

**Preconditions:**
- An order already moved to `DELIVERED` (or any terminal-ish state) via
  ORD-028, or a fresh `PENDING` order and an out-of-order target like
  `SHIPPED`.

**Expected Result:**
- Response status is 409.
- `error.code` is `INVALID_STATUS_TRANSITION`.
- `error.details` carries `from`, `to`, and `allowed` (a list, possibly
  empty for a terminal state).

### ORD-030 — A customer can cancel their own PENDING/CONFIRMED order

**Endpoint:** PATCH /api/v1/orders/{order_id}/status
**Type:** Positive
**Priority:** High

**Expected Result:**
- Response status is 200; `status` is `CANCELLED`.

### ORD-031 — A customer cannot cancel an order that has progressed past CONFIRMED

**Endpoint:** PATCH /api/v1/orders/{order_id}/status
**Type:** Negative / Business rule
**Priority:** Medium

**Preconditions:**
- An order moved to `PROCESSING` (by staff).

**Expected Result:**
- Response status is 409, not 403 - the customer *is* allowed to attempt a
  cancel, the state just no longer permits it.
- `error.code` is `INVALID_STATUS_TRANSITION`.

### ORD-032 — A customer attempting any non-cancel transition gets 403

**Endpoint:** PATCH /api/v1/orders/{order_id}/status
**Type:** Negative / Security
**Priority:** High

**Objective:** Distinct from ORD-031 - here the target status itself
(anything but `CANCELLED`) is never permitted for a customer, regardless
of the order's current state.

**Expected Result:**
- Response status is 403.
- `error.code` is `INSUFFICIENT_PERMISSIONS`.

### ORD-033 — Cancelling releases the reserved stock

**Endpoint:** PATCH /api/v1/orders/{order_id}/status
**Type:** Positive / Side effect
**Priority:** High

**Expected Result:**
- After cancelling, the product's `reserved_stock` (via `GET /inventory`)
  decreases by the order's quantity, back to its pre-order value.
- The order's inventory transactions are `RESERVATION` plus `RELEASE`, so
  the returned stock is traceable to this order rather than just netted
  out of the total.

### ORD-034 — Shipping converts the reservation into a sale without changing available_stock

**Endpoint:** PATCH /api/v1/orders/{order_id}/status
**Type:** Positive / Side effect
**Priority:** High

**Objective:** `_apply_inventory_effect` for `SHIPPED` decrements both
`stock` and `reserved_stock` by the same amount - `available_stock`
(`stock - reserved_stock`) is unchanged by shipping itself, since the
stock was already accounted for as reserved. Verified live: before
`stock=500 reserved=5 available=495`, after shipping one 3-unit line,
`stock=497 reserved=2 available=495` - `available_stock` identical.

**Expected Result:**
- After shipping, `stock` and `reserved_stock` both decrease by the
  order's quantity; `available_stock` is unchanged from just before
  shipping.
- The order's inventory transactions are `RESERVATION` plus `SALE` - the
  numbers alone would also fit a plain adjustment.

### ORD-035 — Cancelling a paid order refunds the payment

**Endpoint:** PATCH /api/v1/orders/{order_id}/status
**Type:** Positive / Side effect
**Priority:** High

**Preconditions:**
- An order with its payment processed to `PAID`
  (`POST .../payment/process`), then cancelled.

**Expected Result:**
- `payment.status` is `REFUNDED` after cancellation.

---

## Status history

### ORD-036 — Status history lists entries chronologically, including the initial PENDING entry

**Endpoint:** GET /api/v1/orders/{order_id}/status-history
**Type:** Positive
**Priority:** Medium

**Objective:** Oldest-first (`created_at`, `id` as a tiebreaker) - the
opposite order from `INV-019`'s inventory transactions, which are
newest-first. Every order's very first entry has `from_status: null`.

**Preconditions:**
- An order transitioned at least once after creation (e.g. cancelled).

**Expected Result:**
- Response status is 200; a plain array (not paginated).
- The first entry has `from_status: null`, `to_status: "PENDING"`.
- Later entries appear in the order they actually happened, oldest first.

### ORD-037 — Status history for an unknown order ID returns 404

**Endpoint:** GET /api/v1/orders/{order_id}/status-history
**Type:** Negative
**Priority:** Low

**Expected Result:**
- Response status is 404.
- `error.code` is `ORDER_NOT_FOUND`.

---

## Payment processing

### ORD-038 — outcome=success marks the payment PAID

**Endpoint:** POST /api/v1/orders/{order_id}/payment/process
**Type:** Positive
**Priority:** High

**Expected Result:**
- Response status is 200.
- `payment.status` is `PAID`; `payment.paid_at` and
  `payment.transaction_reference` are both set (previously `null`).

### ORD-039 — outcome=failure marks the payment FAILED and can be retried afterward

**Endpoint:** POST /api/v1/orders/{order_id}/payment/process
**Type:** Positive / Negative
**Priority:** Medium

**Objective:** `FAILED` is not a terminal state for this endpoint's own
409 guard (only `PAID`/`REFUNDED` are) - a failed mock payment can be
retried to success.

**Expected Result:**
- First call with `outcome=failure`: `payment.status` is `FAILED`.
- A second call with `outcome=success` on the same order: `payment.status`
  becomes `PAID`.

### ORD-040 — Processing an already-processed payment returns 409

**Endpoint:** POST /api/v1/orders/{order_id}/payment/process
**Type:** Negative
**Priority:** Medium

**Preconditions:**
- An order whose payment has already been processed to `PAID`.

**Expected Result:**
- Response status is 409.
- `error.code` is `PAYMENT_ALREADY_PROCESSED`.

