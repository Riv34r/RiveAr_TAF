# Orders — DB Test Scenarios

Source of truth: the live Postgres schema (`pg_constraint`,
`information_schema.columns`) cross-checked against
`backend/app/models/order.py` and `backend/alembic/versions/*` in the
RiveAr App repository - **read, never imported**.

Same shape as the inventory DB scenarios: `test -> DB`, no API, load a
seeded row, mutate/delete inside the `db_session` transaction, assert, roll
back.

Tables in scope: `orders`, `order_items` (+ `customers` for the RESTRICT
check).

---

## Generated columns

### DB-ORD-01 — orders.total follows its formula

**Table:** orders
**Type:** Positive / Invariant
**Priority:** High

**Objective:** `total` is `GENERATED ALWAYS AS (subtotal - discount_total +
tax_total + shipping_total) STORED`. Assert it on every seeded order.

**Expected Result:**
- For every row in `orders`: `total == subtotal - discount_total +
  tax_total + shipping_total`.

### DB-ORD-02 — order_items.line_total follows its formula

**Table:** order_items
**Type:** Positive / Invariant
**Priority:** High

**Objective:** `line_total` is `GENERATED ALWAYS AS (unit_price *
quantity) STORED`. Assert it on every seeded line item.

**Expected Result:**
- For every row in `order_items`: `line_total == unit_price * quantity`.

---

## CHECK constraints

### DB-ORD-03 — a discount cannot drive the order total negative

**Table:** orders
**Type:** Negative / Constraint
**Priority:** High

**Objective:** `ck_orders_total_non_negative` - a CHECK on a *generated*
column, enforcing "a discount can never make an order total negative" at
the database level, not just in application code. Set `discount_total` far
above the order's other amounts; the generated `total` recomputes negative
and Postgres rejects the write.

**Expected Result:**
- `UPDATE orders SET discount_total = 999999.99` on a normal seeded order
  -> `IntegrityError`, constraint `ck_orders_total_non_negative`.

### DB-ORD-04 — an order line's quantity must be positive

**Table:** order_items
**Type:** Negative / Constraint
**Priority:** Medium

**Objective:** `ck_order_items_quantity_positive`. A zero- or
negative-quantity line item is nonsense; the database refuses it.

**Expected Result:**
- `UPDATE order_items SET quantity = 0` -> `IntegrityError`, constraint
  `ck_order_items_quantity_positive`.

---

## Cascade / referential actions

### DB-ORD-05 — deleting an order removes its line items

**Table:** orders, order_items
**Type:** Positive / Referential action
**Priority:** Medium

**Objective:** `order_items.order_id -> orders.id` is `ON DELETE CASCADE`.
Delete a seeded order, confirm its items are gone, roll back.

**Expected Result:**
- Before: `SELECT count(*) FROM order_items WHERE order_id = X` is greater
  than 0.
- After `DELETE FROM orders WHERE id = X` (flushed): the same count is 0.

### DB-ORD-06 — a customer with orders cannot be deleted

**Table:** orders, customers
**Type:** Negative / Referential action
**Priority:** Medium

**Objective:** `orders.customer_id -> customers.id` has no `ON DELETE`
action (RESTRICT / NO ACTION). Unlike DB-ORD-05, the FK here protects the
parent: you can't delete a customer while any order references them.

**Expected Result:**
- `DELETE FROM customers WHERE id = <a customer that has orders>` ->
  `IntegrityError` (SQLSTATE 23503, foreign-key violation).

---

## Unique constraints

### DB-ORD-07 — order_number is unique

**Table:** orders
**Type:** Negative / Constraint
**Priority:** Low

**Objective:** `orders.order_number` carries a UNIQUE constraint. Take two
seeded orders and set one's `order_number` to the other's.

**Expected Result:**
- `UPDATE orders SET order_number = <another order's number>` ->
  `IntegrityError` (SQLSTATE 23505, unique violation).
