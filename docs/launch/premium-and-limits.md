# Free vs Premium access and usage limits

## In one paragraph
At launch almost everything is free. Every premium-capable tool already goes through **one server-side
usage engine** (`backend/usage/`). It counts each use in the database, applies the allowance for the
person's plan, and refuses with a clear message when the allowance is used up. Every allowance and switch is
set in the dashboard (**Premium Controls**). Nothing is hard-coded in the tools. To start charging for
Premium later, change numbers and switches in the dashboard. No code change or redesign is needed.

## What is limited at launch (generous on purpose)
| Tool | What counts as one use | Free (signed in) | Premium | Visitors without an account |
|---|---|---|---|---|
| Reference Generator | a successful DOI/URL/title lookup | 100 per day | no limit | not counted |
| Journal Finder | one search | 50 per day | no limit | not counted |
| Sample Size Calculator | opening the results step with new inputs | 100 per day | no limit | not counted |
| Research Analyzer | one analysis run or master-report generation | no limit | 25 per month | cannot use (sign-in required) |

These allowances were already in the database. The launch migration adds the enforcement switches and keeps
these numbers. Saving workspaces, uploading datasets, exporting and viewing never count. Administrators are
never limited.

**Owner decisions before launch (see "Check before launch"):**
1. On a fresh database, Research Analyzer is **Premium-only** for Free users (the original seed). The current
   developer database has it switched to Free. After deploying, open *Premium Controls → Features* and confirm
   the "Free users" switch for Research Analyzer is set the way you want.
2. Research Analyzer allows Premium 25 runs a month but Free has **no** limit. Premium gets less than Free.
   The dashboard now shows a notice about this. Either add a Free limit or raise or remove the Premium one.

## Where to change things (dashboard → Premium Controls)
- **Features**: whether Free or Premium users may use a tool at all. If you switch Free off, the tool becomes
  Premium-only, and the server refuses Free users (403 "premium_required") on every tool endpoint.
- **Usage limits**: the number of uses per tool, per plan (Free/Premium) and per period (day/month/lifetime).
  Example for the "10 a day" plan: Journal Finder, Free, Daily, 10.
- **Enforcement** (new tab): for each tool:
  - *Limits on*: the master switch. Off means nobody is blocked for that tool, and use is still counted, so you
    can see demand before you switch it on.
  - *Visitors (no account)*: count visitors by network address, with an optional daily or monthly visitor limit.
  - *Admins unlimited*: on by default.
  - *Show remaining*: "Always", "Near the limit" (default: when 20% or 3 uses are left) or "Never".
  - *Extra message*: for example "Upgrade to Premium for more searches." This is added to the limit message.
  - Today's use (how many uses, by how many people).
- *Research Analyzer Controls* has the same master switch next to the analyzer quotas.

Changes take effect on the next request. Users do not need to refresh or sign in again.

## Turning on Premium restrictions later (checklist)
1. Connect Stripe and set the Premium price IDs (see the accounts/billing doc).
2. In *Usage limits*, lower the Free numbers (for example 10 per day) and add Premium numbers if you want any.
3. In *Enforcement*, make sure *Limits on* is ticked. If you also want to stop people using tools signed out,
   tick *Visitors* and set a visitor limit.
4. Optionally set an *Extra message* with an upgrade hint.

## How it is protected
- **Refreshing the page, a new tab, or signing out and back in** does not reset anything. Counts are stored in
  the database per user (`usage_usagecounter`), not in the browser.
- **Calling the API directly or editing frontend code**: the reference lookup and Research Analyzer endpoints
  count and refuse on the server. The reference lookup refuses *before* calling Crossref/OpenAlex.
- **Many requests at the same moment**: each increment is one database UPDATE that includes the limit
  (`count <= limit - 1`). Two parallel requests can never both take the last unit, on PostgreSQL or SQLite.
- **When the limit is reached** the API answers HTTP 429:
  `{"code": "usage_limit", "error": "You have used all 10 searches for Journal Finder today. Your allowance resets on 23 Oct 2026 at 00:00 UTC.", "limit": 10, "remaining": 0, "period": "day", "reset_at": "...", "usage": {...}}`
  It also sends a `Retry-After` header. The tools show this message.
- **Visitors** are identified by a one-way keyed hash of their IP address (IPv6 by /64 block). The raw IP is
  never stored.
- A separate per-minute rate limit still protects the lookup and consume endpoints from scripted floods.

### Remaining risk (honest)
**Journal Finder** and **Sample Size Calculator** do their work in the browser: the journal list and the
formulas ship with the page. The server counts each search or calculation before results are shown, so normal
use, refreshes and API calls are all counted. A technical user could still run the browser code directly and
skip the count. The only full fix is to move the matching or calculation to the server. That is a larger
change and is not worth doing while these tools are free. Do it before making either tool Premium-only if
that matters. Signed-out use of these two tools is only counted if you switch on *Visitors* for them.
Visitor counting by IP is approximate: people on a shared network share one allowance, and VPN users can
change address.

## API reference (for developers)
- `GET /api/usage/`: allowance for every metered tool for the current user or visitor.
- `GET /api/usage/<feature>/`: one tool, for example `{"used_today": 3, "limit": 10, "remaining": 7, "reset_at": "...", "plan": "free", "unlimited": false}`.
- `POST /api/usage/<feature>/consume/`: browser-side tools only (`journal_finder`, `sample_size_calculator`).
- `GET /api/usage/admin/policies/`, `POST /api/usage/admin/policies/<feature>/save/`: dashboard (needs
  `settings.read` / `settings.write`).
- Code: `usage.services.gate(request, feature, action)` charges now; `precheck(...)` refuses early without
  charging; `@metered(feature, action)` is a view decorator. `METERED_ACTIONS` in `usage/services.py` is the one
  list of actions that count. The old `accounts.entitlements.meter_action/consume_usage` helpers forward to
  the same engine.
- Existing usage history (`UsageRecord`) was copied into the new counters by the migration, so today's and
  this month's use carries over when you deploy.

## Environment variables
| Name | Purpose | Example |
|---|---|---|
| `RESREF_USAGE_TIMEZONE` (optional) | Time zone for midnight and month resets. Default `UTC`. | `Asia/Dubai` |

## Check before launch (after Railway is back)
- [ ] `migrate` runs `usage.0001_initial` and `usage.0002_seed_launch_policies`. Both are additive.
- [ ] Premium Controls → Enforcement lists 4 tools, each with "Limits on" ticked.
- [ ] Decide on Research Analyzer Free access and the Free/Premium imbalance (see above).
- [ ] Signed in as a Free test user, run Journal Finder once, then check `GET /api/usage/journal_finder/` shows `used_today: 1`.
