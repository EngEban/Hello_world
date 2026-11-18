# Accounts and email — launch notes

Owner: accounts audit. Code: `backend/accounts/`, `frontend/src/pages/account/`, `frontend/src/components/account/`.

## Before launch (must do)

1. **Connect Brevo SMTP** (Railway variables):

   | Variable | Example | Purpose |
   |---|---|---|
   | `DJANGO_EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` | Real sending (production refuses to start on console/locmem) |
   | `DJANGO_EMAIL_HOST` | `smtp-relay.brevo.com` | Brevo SMTP relay |
   | `DJANGO_EMAIL_PORT` | `587` | STARTTLS port |
   | `DJANGO_EMAIL_USE_TLS` | `true` | |
   | `DJANGO_EMAIL_HOST_USER` | *(Brevo SMTP login)* | secret |
   | `DJANGO_EMAIL_HOST_PASSWORD` | *(Brevo SMTP key)* | secret |
   | `DJANGO_DEFAULT_FROM_EMAIL` | `ResRef <no-reply@resref.com>` | Sender of every account email. The domain must be verified in Brevo (SPF + DKIM, and a DMARC record) or mail lands in spam. |

2. **`ACCOUNT_EMAIL_CONFIRMATION_REQUIRED` must be `true` at launch** (it is `true` when unset).
   `false` is a temporary switch for running without email: new sign-ups are signed in immediately
   without proving they own the address, and the sign-up answer reveals whether an address was new.
   Accounts created while it was `false` stay "Email verification pending" (they are not locked out);
   they can verify from the account page.
3. After SMTP is connected, test on staging: sign up → confirmation email → link signs you in;
   "Forgot password" email; change password (you get a "password was changed" email); change email
   (link goes to the new address, old address is told); Google sign-in (if `GOOGLE_OAUTH_CLIENT_ID` is set).

## Optional variables

| Variable | Default | Purpose |
|---|---|---|
| `ACCOUNT_NEW_SIGNIN_EMAILS` | `true` | Email the member when their account signs in from a browser not seen before. Set `false` to reduce email volume (Brevo free plan: 300/day). |
| `EMAIL_TIMEOUT` (Django setting) | 15 s used by account email | SMTP timeout so a slow mail server cannot hang sign-ups. |

## What members can do

- Sign up (name, email, password, **country — required**, **phone — optional**), confirm by email, sign in,
  "Keep me signed in" (unticked = session ends when the browser closes; ticked = 7-day sliding session).
- Google sign-in (links to an existing account only when the email is verified; see S-03 notes in code).
- Account page: edit name, organisation, country, phone; change password; change email (re-verified);
  download all their data (JSON); delete account.

### Country and phone

- Country: ISO 3166-1 alpha-2 code (plus `XK` Kosovo), validated on the server. The sign-up form pre-selects
  it from the browser language (e.g. `en-GB` → United Kingdom); it is required in the form because it helps
  ResRef understand its audience, while the API still accepts it empty so Google sign-ups and older apps work.
- Phone: optional (not needed to use the platform; asking for it at sign-up lowers conversions). Validated with
  Google's libphonenumber (`phonenumbers` on the server, `react-phone-number-input` in the browser) and stored
  in international E.164 form, e.g. `+447911123456`.

### Account deletion (how it works)

Deletion never removes database rows. The login is deactivated, the password removed, and personal data is
overwritten (email, name, username, display name, avatar, organisation, specialization, country, phone,
Google link). Newsletter mail to the old address is paused. Billing history, audit logs and other records stay
but no longer identify the person. Blocked for staff/team accounts and for active paid subscriptions (cancel
first). A confirmation email goes to the old address.

**Owner decision:** saved tool workspaces, notifications and usage counts are kept (linked to the anonymised
account). If you want them erased too, approve a purge step and it can be added.

## Security behaviour (for reference)

- Login issues a new session id (no session fixation); logout deletes the session.
- Password change keeps the current device signed in and signs out all others; password reset signs out all.
- Both send a "Your ResRef password was changed" email + in-app notice.
- Brute force: sign-in limited per IP+account (8/15 min), per account (20/h), per IP (60/15 min);
  password change, email change, Google linking and deletion are rate-limited per account.
- No account enumeration: sign-up, password reset, confirmation resend and email change give the same answer
  whether or not an address exists (and sign-up takes the same time).
- Password policy: at least 12 characters, not common, not all digits, not similar to the name/email,
  not one of the last 5 passwords.
- Every account email is sent as plain text + HTML through the Django email backend, from
  `DJANGO_DEFAULT_FROM_EMAIL`. Emails never contain passwords.

## API fields (for the dashboard)

`GET /api/accounts/me/` → `account` now also has:
`country` (e.g. `"GB"` or `""`), `country_name` (e.g. `"United Kingdom"`), `phone_number` (E.164 or `""`),
`has_password` (bool). The model fields are `MembershipProfile.country`, `.phone_number`, `.deleted_at`
(set when the member deleted their account).

New endpoints: `POST /api/accounts/email/` `{new_email, current_password}`, `POST /api/accounts/email/confirm/`
`{token}`, `GET /api/accounts/export/`, `POST /api/accounts/delete/` `{confirm: "DELETE", current_password}`.
`POST /api/accounts/login/` accepts `remember` (default `true`). `POST /api/accounts/register/` and
`/profile/` accept `country` and `phone_number`.
