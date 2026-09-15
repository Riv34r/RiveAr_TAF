# Login — UI Test Scenarios

Source of truth: the running front end, cross-checked against
`frontend/src/pages/LoginPage.tsx`, `frontend/src/components/layout/ProtectedRoute.tsx`,
`frontend/src/context/AuthContext.tsx`, `frontend/src/api/client.ts`,
`frontend/src/api/tokenStorage.ts` and `frontend/src/components/layout/Navbar.tsx`
in the RiveAr App repository - **read, never imported**. Messages and redirects
were checked on the live front end; the paths that need a successful login
were checked against the code only.

These cover what only the browser can get wrong: what the login screen shows,
what it refuses to send, where the app navigates, and whether the browser
keeps, renews or drops a session. What the API decides on its own is
referenced, not repeated - credentials (AUTH-007 to AUTH-011), token rejection
(AUTH-021 to AUTH-023), refresh rotation (AUTH-012, AUTH-013) and logout
revocation (AUTH-017) in `tests/api/scenarios/auth.md`.

Routes in scope: `/login`, and the storefront's protected routes `/orders` and
`/orders/:orderId`. `/checkout` and `/order-confirmation/:orderId` sit behind
the same guard but belong to checkout.

---

## Login form

### UI-LOGIN-01 — Valid credentials sign the customer in and the session survives a reload

**Route:** /login
**Type:** Positive
**Priority:** High

**Objective:** The one full pass through the form: credentials go in, the app
shows the customer as signed in, and the session is still there after a
reload. With no page asked for beforehand, the customer lands on the
storefront home. A login that only held the session in memory would pass
without the reload.

**Preconditions:**
- The browser holds no session.
- The seeded CUSTOMER account and the shared password, from the seed manifest.

**Expected Result:**
- The browser lands on the storefront home, `/`.
- The navbar shows the account menu in place of the Log in link.
- After a reload, the navbar still shows the account menu.

### UI-LOGIN-02 — A rejected login is reported on the form and the customer can try again

**Route:** /login
**Type:** Negative
**Priority:** High

**Objective:** A credentials rejection reaches the customer as the API worded
it, and leaves the form ready for another attempt. Checking only that "an
error appears" would also pass on the front end's own fallback text or a
generic failure. An unknown email and a disabled account are the API's to
tell apart (AUTH-009, AUTH-010); the form renders whatever message comes back
the same way, so they are not repeated here.

**Preconditions:**
- The browser holds no session.
- The seeded CUSTOMER account's email and a password that is not its own.

**Expected Result:**
- The form shows the message "Incorrect email or password."
- The URL stays `/login`.
- The email field still holds the entered email.
- The Log in button is enabled again.

### UI-LOGIN-03 — The form rejects empty and malformed input before sending anything

**Route:** /login
**Type:** Negative / Validation
**Priority:** Medium

**Objective:** The form checks required fields and the email format itself.
What sets this apart from AUTH-011 is that nothing is sent - an API rejection
would also surface on the form, so the network has to be observed, not only
the messages.

**Preconditions:** Parametrized - each case is independent:
- Both fields left empty.
- A malformed email (e.g. `not-an-email`) with a password filled in.

**Expected Result:**
- With both fields empty, the email field reports "Email is required." and the password field reports "Password is required."
- With a malformed email, the email field reports "Enter a valid email address."
- No request reaches `/auth/login` in either case.
- The URL stays `/login`.

---

## Protected routes

### UI-LOGIN-04 — An anonymous visitor is sent to log in and brought back to the page they asked for

**Route:** /orders/:orderId
**Type:** Negative / Security
**Priority:** High

**Objective:** With no session, a protected route redirects to the login
screen instead of rendering the page, and logging in from there returns the
customer to that exact page rather than the home page. A link to a single
order is used so the full path has to survive the detour, not just `/orders`.

**Preconditions:**
- The browser holds no session.
- An order belonging to the seeded CUSTOMER, with its id and order number, taken from the API.
- The seeded CUSTOMER account and the shared password, from the seed manifest.

**Expected Result:**
- Opening `/orders/<order id>` lands on `/login`.
- The login form is shown, and the order is not.
- After logging in with the CUSTOMER's credentials, the browser is at `/orders/<order id>`.
- The page shows that order's number.

### UI-LOGIN-05 — A session handed to the browser opens a protected route directly

**Route:** /orders
**Type:** Positive
**Priority:** High

**Objective:** A token pair taken over the API and placed in the browser's
storage is accepted as a signed-in session. Every later UI test starts from
this instead of the form, so it is proven once, here.

**Preconditions:**
- A token pair for the seeded CUSTOMER, from `POST /auth/login`, placed in the browser's storage before the page loads.

**Expected Result:**
- `/orders` opens and stays at `/orders`, with no redirect to `/login`.
- The customer's order history is listed.
- The navbar shows the account menu.

---

## Session lifecycle

### UI-LOGIN-06 — Logging out ends the session in the browser

**Route:** /orders
**Type:** Positive
**Priority:** High

**Objective:** Logging out from a protected page drops the session the
browser holds, not only what is on screen, so a later page load does not
bring it back. Revoking the refresh token on the server is AUTH-017.

**Preconditions:**
- A token pair for the seeded CUSTOMER, placed in the browser's storage before the page loads.
- The customer is on `/orders`.

**Expected Result:**
- Choosing "Log out" from the account menu lands on the storefront home, `/`.
- The navbar shows the Log in link in place of the account menu.
- Opening `/orders` again lands on `/login`.

### UI-LOGIN-07 — A stored session the API rejects is treated as signed out

**Route:** /orders
**Type:** Negative
**Priority:** High

**Objective:** When the browser starts with tokens that no longer work, it
shows the login screen rather than the protected page or an endless loading
state, and drops the tokens so they are not tried again. That the API rejects
them is AUTH-023; this covers what the browser does with the rejection.

**Preconditions:**
- An access token for the seeded CUSTOMER that has already expired, from `POST /test/token` with a short lifetime.
- A refresh token the API rejects (a malformed value).
- Both placed in the browser's storage before the page loads.

**Expected Result:**
- Opening `/orders` lands on `/login`.
- The login form is shown.
- Neither token remains in the browser's storage.

### UI-LOGIN-08 — An access token that lapses mid-visit is renewed without interrupting the customer

**Route:** /orders
**Type:** Positive
**Priority:** High

**Objective:** Access tokens last 30 minutes, so any longer visit crosses an
expiry. When a request fails on the expired token, the front end renews the
session with the refresh token and retries, and the customer never notices.
The changed refresh token in storage is what proves a renewal happened -
without it, an access token that had not lapsed yet would pass just as well.
The URL alone proves nothing: it changes to `/orders` on the click, before the
renewal resolves. Rotation itself is AUTH-012 and AUTH-013.

**Preconditions:**
- The seeded CUSTOMER is signed in with a valid token pair and is on the storefront home, `/`.
- An access token for the same customer that has already expired, from `POST /test/token`.
- Mid-visit, the access token in the browser's storage is replaced with the expired one. The front end reads the token from storage on every request, so this is the state a lapsed token leaves - without racing a short lifetime against the page load.

**Expected Result:**
- Going to order history from the account menu, without a reload, opens `/orders` with no redirect to `/login`.
- The customer's order history is listed.
- The refresh token in the browser's storage is no longer the one handed in.

### UI-LOGIN-09 — A session that cannot be renewed mid-visit sends the customer to log in

**Route:** /orders
**Type:** Negative
**Priority:** Medium

**Objective:** When renewal fails as well, the front end signs the browser
out and shows the login screen, rather than leaving a protected page broken
behind an error.

**Preconditions:**
- The seeded CUSTOMER is signed in with a valid access token and a refresh token the API rejects (a malformed value), and is on the storefront home, `/`.
- Mid-visit, the access token in the browser's storage is replaced with one for the same customer that has already expired, from `POST /test/token`.

**Expected Result:**
- Going to order history from the account menu, without a reload, lands on `/login`.
- Neither token remains in the browser's storage.

### UI-LOGIN-10 — A reload after the access token lapses signs the customer out, even with a renewable session

**Route:** /orders
**Type:** Negative
**Priority:** Medium

**Known defect:** [BUG-005](../../../BUGS.md#bug-005), accepted for now. On
load the front end checks the session with `GET /auth/me`, and the renewal in
`frontend/src/api/client.ts` skips every `/auth/` path, so a refresh token the
API would still honour is never tried. This scenario describes the behaviour
as it is and flips to "stays signed in" once BUG-005 is fixed. It differs
from UI-LOGIN-07 only in the refresh token - rejected there, valid here - which
is what makes the fix show up here and nowhere else.

**Objective:** A customer who reloads, or comes back to the storefront, after
the 30-minute access token has lapsed is signed out and sent to log in,
although their refresh token is still valid for days.

**Preconditions:**
- A token pair for the seeded CUSTOMER, from `POST /auth/login`, with its access token swapped for one from `POST /test/token` that has already expired.
- Both placed in the browser's storage before the page loads.

**Expected Result:**
- Opening `/orders` lands on `/login`.
- No request reaches `/auth/refresh`.
- Neither token remains in the browser's storage.
