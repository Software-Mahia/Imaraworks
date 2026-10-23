# Part B: approval workflow (presentation notes)

Part B decides **who may approve or reject a payment request, and when it counts as approved**. It covers role-based permissions, the 50,000 KES tiers, the self-approval block, rejection reasons, and re-approval when the amount changes.

Code: `apps/approvals/` (`logic.py`, `services.py`, `views.py`, `models.py`). API: [APPROVALS_API.md](APPROVALS_API.md).

## The rules, and where each one lives

| Rule | Enforced in | Proved by |
|---|---|---|
| ≤ 50,000 needs one manager; > 50,000 needs a manager **and** finance | `required_levels()` in `logic.py` | `test_approval_logic`: 24,500 / 42,000 / 67,000 / 148,000, exactly 50,000, just over |
| Nobody approves their own request | `evaluate_approval()` check 3 | `test_cannot_approve_own_request`, `test_self_approval_is_refused_and_nothing_written` |
| A rejection needs a reason, and it is recorded | `decide_rejection()`, plus the `rejection_requires_reason` constraint | `test_reject_action`, `test_approval_model` |
| Changing the amount after approval forces re-approval, and re-tiers across 50,000 | `decide_amount_change()` | `test_amount_change_action`, `test_approval_flow` |
| Only managers and finance approve, each at their own level | `evaluate_approval()` checks 1 and 4 | `test_approvals_api` (`test_each_refusal_maps_to_its_status`) |
| Every approve and reject writes an audit entry | `approve()` / `reject()`, in the same transaction | `test_approval_writes_one_audit_entry`, `test_rejection_writes_audit_entry_with_reason` |

## How a request moves

```
DRAFT --submit--> PENDING_APPROVAL --last required approval--> APPROVED --> (Part C pays it)
                      |    ^
                 reject    |  amount changed (approvals superseded)
                      v    |
                  REJECTED  +-- from PENDING_APPROVAL or APPROVED
```

- Submit goes straight from DRAFT to PENDING_APPROVAL (agreed on PR #5). A separate SUBMITTED step would be a second click with no rule behind it.
- One rejection at any level ends the request. Approval needs **every** required level.

## Design decisions (what I'd say if asked "why?")

### 1. Three layers: rules, orchestration, HTTP
**Concept:** separation of concerns.
- `logic.py` holds the rules as **pure functions**: plain data in, an answer out, with no database and no HTTP.
- `services.py` does "decide, then save". `decide_approval()` is pure and returns a frozen `ApprovalDecision`, and `approve()` writes exactly what it says.
- `views.py` only translates: HTTP in, a service call, HTTP out.

**Problem it solves:** the rules are what the brief grades, so they must be easy to test. Pure functions are tested without a database, fake requests or fixtures.
**Trade-off:** more files and a little indirection. In return, there's one place to read each rule, and the tests are fast.

### 2. The tier comes from the *current* amount, every time
`required_levels(amount)` is recalculated on every check; it is never stored. So re-tiering after an amount change needs **no special code**: raise 42,000 to 67,000 and the next check simply asks for finance too.
**Trade-off:** none really. Storing the tier would have meant keeping it in sync, which is the bug this avoids.

### 3. Role vs level
A **role** is what you are (MANAGER, FINANCE); a **level** is what your approval contributes (`manager`, `finance`). `ROLE_TO_LEVEL` is the one place that maps them. Employees and admins aren't in it, so they can't approve.
The level is **stored on the Approval row**, so if someone's role changes later, history doesn't change with it.

### 4. One gate for approve *and* reject
Rejecting is the same decision with the other answer, so it goes through the same `evaluate_approval()` checks: role, pending, not your own request, your level is needed, your level hasn't already approved.
**Problem it solves:** two separate permission rules would drift apart.
The permission check runs **before** the reason check, so someone who can't reject is told so, not asked for a reason.

### 5. Checks run in a fixed order, and the first failure is reported
1. Role can't approve → 403
2. Not pending → 409
3. Your own request → 403
4. Your level isn't needed → 403
5. Your level already approved → 409

The HTTP status follows a rule: **403 = "not you"** (it will never be allowed), **409 = "not now"** (the state changed, so reload), **400 = "fix your input"** (e.g. a blank reason).

### 6. Superseded, not deleted
When the amount changes, earlier approvals are marked `superseded=True`. They're never deleted, so the history still shows who approved the old amount. **Any** change, even a decrease, invalidates approvals: approvers approved a specific number.
After a request is REJECTED, or once payment has started, the amount is locked (409). Changing it then would break "paid amount = approved amount".

### 7. Two layers of protection against double approval
- **Row lock:** `approve()` re-reads the request with `select_for_update()` inside a transaction. If two managers click at once, they're handled one after the other, and the second sees the first's approval (409).
- **Database constraint:** `one_active_approval_per_level` allows at most one counting approval per level. If the lock is ever bypassed, the database refuses the second row, and `approve()` turns that into the same 409 (PR #45).

**Concept:** defence in depth. The service checks first and gives a clear message; the database guarantees the rule regardless.

### 8. All-or-nothing writes
The Approval row, the status change and the audit entry are written in **one transaction**. Refusals are exceptions (`ApprovalDenied`), so leaving the transaction rolls back anything written. A refused action leaves **no trace**, and tests check exactly that (`assert_nothing_written`).

### 9. The approval queue reuses the rules
`approval_queue(user)` runs every pending request through the same `evaluate_approval()` that `approve()` uses, rather than restating the rules as a database filter. So the queue **can never list a request that approve would then refuse**. Approvals are prefetched, so the list costs a fixed number of queries (`test_list_query_count_does_not_grow_with_requests`).

### 10. Small things that prevent real bugs
- **Money is `Decimal`,** never float, so 50,000.00 compares exactly.
- **Roles, statuses and audit actions come from the models' constants** (golden rule 1), so a renamed value can't silently break a rule.
- **Reasons are trimmed,** and whitespace-only counts as empty.
- **You can't act on a request you can't see.** The views look it up through `visible_requests()`, so another employee's request is a 404 (not a 403 that confirms it exists).

## Related rules from the team (built with Part C)

- **No paying your own request:** Finance gets a 403 for a request they raised. It's the same separation-of-duties idea as the self-approval block (decided on #33, built in PR #44).
- **Second Finance user (`fiona`):** without her, nobody could pay faith's requests, and her requests over 50,000 could never get a finance approval (#15). Added in PR #44.

## Known limitations (say these before someone else does)

- **CI and local development use SQLite, which ignores row locks.** The lock only really works on PostgreSQL in production. The database constraint covers approvals either way, and the race test simulates the clash rather than running real threads.
- **No `submitted_at` yet,** so the queue can't show how long a request has waited (#40).
- **Report date range:** whether reports filter by request date or payment date is still open (#41).

## Demo script (about 3 minutes)

Seed users: `python manage.py seed_users` (password `password123`, local only).

1. **≤ 50,000:** alice raises 24,500 and submits it. carol approves it, and it's APPROVED.
2. **> 50,000:** alice raises 148,000. carol approves, and it's still PENDING, waiting on finance. faith approves, and it's APPROVED. (It works in either order.)
3. **Self-approval:** carol raises her own request and tries to approve it: 403, "You cannot approve a request you created."
4. **Rejection:** david rejects one with a blank reason: 400. With a reason, it's REJECTED, and the reason shows in the history.
5. **Amount change** (`PATCH /api/payment-requests/<id>/amount/`): alice raises an approved 42,000 request to 67,000. It goes back to PENDING and now needs carol (or david) **and** faith.

## Likely questions

- **Why not put the rules in the views?** Then testing a rule would mean faking HTTP, and the queue and approve could disagree. One pure function serves both.
- **Why is a decrease re-approved?** The approver approved a specific amount. "Any change" is a simple rule that's easy to audit; "only increases" invites arguments about what counts.
- **What if two managers approve at the same instant?** The row lock serialises them, and the second gets 409. If the lock is ever bypassed, the database constraint refuses the second row, and it's still a 409.
- **Can finance approve a small request?** No: finance isn't a required level at or below 50,000, so it's a 403 ("Your approval is not required").
- **Why can an admin not approve?** Admin is a system role, not an approver. It has no level in `ROLE_TO_LEVEL`.
- **How do you know the audit log is trustworthy?** Entries can't be edited or deleted, through the model or in bulk (`test_audit_log`). A request with history can't be deleted either.

## Tests

The whole suite runs with `python manage.py test` (CI runs it on every PR). The Part B test files:

| File | What it covers |
|---|---|
| `test_approval_logic.py` | The pure rules, with the case-study numbers and the 50,000 boundary |
| `test_approval_services.py` | Decide-then-save outcomes for approve, reject and amount change |
| `test_approve_action.py`, `test_reject_action.py`, `test_amount_change_action.py` | What gets written, and that nothing is written when refused |
| `test_approvals_api.py`, `test_amount_api.py` | HTTP status codes, response shapes, 404 for requests you can't see |
| `test_approval_flow.py` | End-to-end scenarios across several users |
| `test_approval_model.py` | The database constraints |
| `test_approval_queue.py` | The queue and the approval block |
