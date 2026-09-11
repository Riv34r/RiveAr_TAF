# Login — UI Test Scenarios

Source of truth: the running front end, cross-checked against
`frontend/src/pages/LoginPage.tsx`, `frontend/src/components/layout/ProtectedRoute.tsx`
and `frontend/src/api/tokenStorage.ts` in the RiveAr App repository - **read,
never imported**.

These cover what only the browser can get wrong: what the form shows, where
the app navigates, and whether it treats a session as signed in. The
credential rules themselves are the API's, already covered by AUTH-007
through AUTH-011 in `tests/api/scenarios/auth.md`.

Routes in scope: `/login`, and `/orders` as a representative protected route.

---

## Login form

### UI-LOGIN-01 — Valid credentials sign the customer in

**Route:** /login
**Type:** Positive
**Priority:** High

**Objective:** The one full pass through the form: credentials go in, a
session comes back, and the app shows the customer as signed in.

**Preconditions:**
- The seeded CUSTOMER account and its password, from the seed manifest.

**Expected Result:**
- The browser lands on the storefront home, `/`.
- The navbar shows the signed-in user menu in place of the log-in button.

### UI-LOGIN-02 — A wrong password is reported and keeps the customer on the form

**Route:** /login
**Type:** Negative
**Priority:** High

**Objective:** A rejected login is shown to the customer rather than failing
silently, and does not navigate away from the form.

**Preconditions:**
- The seeded CUSTOMER account's email.

**Expected Result:**
- An error message appears on the form.
- The URL stays `/login`.

### UI-LOGIN-03 — A malformed email is rejected in the browser, before any request

**Route:** /login
**Type:** Negative / Validation
**Priority:** Medium

**Objective:** The form validates the email itself. The claim that sets this
apart is that nothing is sent - a rejection from the API would look much the
same on screen, so the network has to be observed, not only the message.

**Expected Result:**
- The email field reports "Enter a valid email address."
- No request reaches `/auth/login`.

---

## Protected routes

### UI-LOGIN-04 — A protected route sends an anonymous visitor to the login screen

**Route:** /orders
**Type:** Negative / Security
**Priority:** High

**Objective:** With no session, a protected route redirects to the login
screen instead of rendering the page or an error.

**Preconditions:**
- No session in the browser.

**Expected Result:**
- The URL becomes `/login`.
- The login form is shown.

### UI-LOGIN-05 — A session handed to the browser opens a protected route directly

**Route:** /orders
**Type:** Positive
**Priority:** High

**Objective:** A token pair taken over the API and placed in the browser's
storage is accepted as a signed-in session. Every later UI test starts from
this instead of the form, so it is proven once, here.

**Preconditions:**
- A token pair for the seeded CUSTOMER, from `POST /auth/login`.

**Expected Result:**
- `/orders` opens and stays at `/orders`, with no redirect to `/login`.
- The navbar shows the signed-in user menu.
