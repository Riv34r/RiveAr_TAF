# Inventory — DB Test Scenarios

Source of truth: the live Postgres schema (`pg_constraint`,
`information_schema.columns`) cross-checked against
`backend/app/models/inventory.py` and `backend/alembic/versions/*` in the
RiveAr App repository - **read, never imported**.

These test rules the database enforces itself, with no API involved
(`test -> DB`). Every test loads a row that `POST /test/reset` already
seeded, mutates or deletes it inside the `db_session` transaction, asserts,
and the fixture rolls the transaction back - nothing a test does outlives
it.

Tables in scope: `inventory` (+ `inventory_transactions` for the cascade
check).

---

## Generated columns

### DB-INV-01 — available_stock is always stock minus reserved_stock

**Table:** inventory
**Type:** Positive / Invariant
**Priority:** High

**Objective:** `available_stock` is a `GENERATED ALWAYS AS (stock -
reserved_stock) STORED` column - computed by Postgres, never written by the
application. Asserting it on every seeded row (not one hand-picked) proves
the formula holds across the whole dataset.

**Expected Result:**
- For every row in `inventory`: `available_stock == stock - reserved_stock`.

---

## CHECK constraints

### DB-INV-02 — reserved_stock cannot exceed stock

**Table:** inventory
**Type:** Negative / Constraint
**Priority:** High

**Objective:** `ck_inventory_reserved_not_exceeding_stock` - the real
business invariant (you can't reserve more units than you physically have).
Isolable: set `reserved_stock = stock + 1` on a row whose `stock` is
positive, so no other constraint is tripped at the same time.

**Expected Result:**
- `UPDATE inventory SET reserved_stock = stock + 1` -> `IntegrityError`,
  constraint `ck_inventory_reserved_not_exceeding_stock`.

### DB-INV-03 — reserved_stock cannot be negative

**Table:** inventory
**Type:** Negative / Constraint
**Priority:** Medium

**Objective:** `ck_inventory_reserved_stock_non_negative`. Isolable on a row
with positive `stock`: `reserved_stock = -1` still satisfies `reserved_stock
<= stock`, so only the non-negative check fires.

**Expected Result:**
- `UPDATE inventory SET reserved_stock = -1` -> `IntegrityError`,
  constraint `ck_inventory_reserved_stock_non_negative`.

*(`ck_inventory_stock_non_negative` is deliberately not tested on its own -
`reserved_stock >= 0` plus `reserved_stock <= stock` already implies
`stock >= 0`, so a dedicated test would only be exercising Postgres.)*

---

## Foreign keys

### DB-INV-04 — product_id must reference a real product

**Table:** inventory
**Type:** Negative / Constraint
**Priority:** Medium

**Objective:** The `inventory.product_id -> products.id` foreign key. Point
an existing row at a random UUID that no product has.

**Expected Result:**
- `UPDATE inventory SET product_id = <random uuid>` -> `IntegrityError`
  (SQLSTATE 23503, foreign-key violation).

---

## Cascade behavior

### DB-INV-05 — deleting an inventory record removes its transactions

**Table:** inventory, inventory_transactions
**Type:** Positive / Referential action
**Priority:** Medium

**Objective:** `inventory_transactions.inventory_id -> inventory.id` is
declared `ON DELETE CASCADE`. Pick a seeded inventory row that has at least
one transaction, delete it, confirm its transactions are gone too - then
roll back.

**Expected Result:**
- Before: `SELECT count(*) FROM inventory_transactions WHERE inventory_id
  = X` is greater than 0.
- After `DELETE FROM inventory WHERE id = X` (flushed, not committed): the
  same count is 0.
