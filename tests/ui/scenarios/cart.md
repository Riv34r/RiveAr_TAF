# Cart — UI Test Scenarios

Source of truth: the running front end, cross-checked against
`frontend/src/utils/guestCart.ts`, `frontend/src/context/CartContext.tsx`,
`frontend/src/pages/CartPage.tsx`, `frontend/src/pages/ProductDetailPage.tsx`,
`frontend/src/pages/CheckoutPage.tsx` and `backend/app/services/cart_service.py`
in the RiveAr App repository - **read, never imported**. Checked against the
code only so far; messages are quoted from it.

These cover what only the browser can get wrong: a guest's cart, which has no
backend counterpart and lives in the browser's storage alone, and the hand-over
of that cart to the customer's own cart when they log in. What the server
decides when an item is added - summing quantities, refusing an inactive or
out-of-stock product - belongs to the API's cart domain, which has no scenarios
yet; checking out a cart is ORD-021 to ORD-023 in `tests/api/scenarios/orders.md`.

Routes in scope: `/products/:productId` (adding to the cart), `/cart`, and
`/checkout` as far as reaching it with the cart. The checkout steps and placing
an order belong to checkout. That checkout sends a customer with an empty cart
back to `/cart` has no scenario: no page in the app leads to checkout with an
empty cart, and opening it directly is BUG-006, which redirects whatever the
cart holds; ORD-022 covers the server refusing it.

A customer in these scenarios is a disposable one with an empty cart. The
server sums what a login carries over into the cart, so the seeded CUSTOMER
would collect more on every run.

---

## Guest cart

### UI-CART-01 — A product a guest adds is in the cart once and survives a reload

**Route:** /products/:productId, /cart
**Type:** Positive
**Priority:** High

**Objective:** A guest's cart exists only in the browser, so only the UI can
show that it keeps what was added. Adding one and then two more of the same
product catches a cart that stores the product but not how many, counts lines
instead of items, or gives a repeated product a second line - which would reach
the customer's cart as two separate additions on login. The reload catches a
cart held only in memory.

**Preconditions:**
- The browser holds no session and no guest cart.
- A disposable active product with stock and no category, so its page shows no related products.

**Expected Result:**
- After adding one of the product from its page and then two more, the navbar's cart count shows 3.
- The cart lists the product once, with quantity 3 and a line total of three times its price.
- After a reload, the cart still lists the product once, with quantity 3.

---

## Carrying the cart over on login

### UI-CART-02 — Logging in carries the guest cart into the customer's cart exactly once

**Route:** /login, /cart
**Type:** Positive
**Priority:** High

**Objective:** On login the front end replays each guest line through the
server, which adds it to the customer's cart, and then empties the guest cart.
The server sums what it is given, so a line replayed twice - on every page load
while the guest cart was never emptied, say - doubles the quantity. Checking
that the product is merely present would pass on that; the exact quantity does
not.

**Preconditions:**
- A disposable customer with an empty cart.
- The browser holds no session, and the guest cart holds two of a disposable active product with stock.

**Expected Result:**
- After logging in, the guest cart the browser held is empty.
- The cart lists the product with quantity 2.
- After a reload, the cart still lists the product with quantity 2.

### UI-CART-03 — A guest line the server refuses is dropped on login and the customer is told

**Route:** /login, /cart
**Type:** Negative
**Priority:** Medium

**Objective:** A line the server refuses is removed from the guest cart and
the customer gets a warning, while the lines it accepts still arrive. Without
the removal the refused line would be tried again on every page load; without
the warning it would vanish unnoticed. Why the server refuses it is the API's
to decide.

**Preconditions:**
- A disposable customer with an empty cart.
- The browser holds no session, and the guest cart holds one of a disposable active product with stock and one of the seeded out-of-stock product - put into the browser's storage directly, since the out-of-stock product's page does not let a guest add it.

**Expected Result:**
- After logging in, the customer sees the warning "One item from your cart couldn't be added — it may be out of stock or no longer available."
- The guest cart the browser held is empty.
- The cart lists only the product that was in stock, with quantity 1.

---

## Checkout

### UI-CART-04 — A guest proceeding to checkout logs in and comes back to checkout with the cart

**Route:** /cart, /login, /checkout
**Type:** Positive
**Priority:** High

**Objective:** Checkout is behind the login guard, and it sends a customer
with an empty cart back to `/cart`. A guest who proceeds to checkout must land
back on checkout after logging in, with the cart they built. The return itself
is the mechanism UI-LOGIN-04 covers; here it matters because the cart has to
be carried over before checkout decides the cart is empty. That the cart
reaches the server exactly once is UI-CART-02; a reload of checkout itself is
UI-CART-06.

**Preconditions:**
- A disposable customer with an empty cart.
- The browser holds no session, and the guest cart holds two of a disposable active product with stock, added from its page.

**Expected Result:**
- Proceeding to checkout from the cart lands on `/login`.
- After logging in, the browser lands on `/checkout`.
- The checkout's order summary lists the product with quantity 2.

### UI-CART-06 — Reloading checkout sends a customer with a full cart back to the cart

**Route:** /cart, /checkout
**Type:** Negative
**Priority:** Medium

**Known defect:** [BUG-006](../../../BUGS.md#bug-006), open. On a page load
checkout decides the cart is empty before the customer's cart has loaded, and
redirects to `/cart`. This scenario describes the behaviour as it is and flips
to "checkout stays open with the cart" once BUG-006 is fixed.

**Objective:** A customer who reloads checkout - or opens it from a link - is
sent back to the cart even though the cart holds items. Reaching checkout from
the cart inside the app is unaffected (UI-CART-04).

**Preconditions:**
- A disposable customer whose cart holds two of a disposable active product with stock, put there through the API.

**Expected Result:**
- After logging in and proceeding to checkout from the cart, checkout shows the order summary.
- After a reload, the browser lands on `/cart`.
- The cart still lists the product with quantity 2.
