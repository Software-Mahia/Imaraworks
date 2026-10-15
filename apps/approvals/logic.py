"""Pure approval rules for Part B (the ``logic`` layer in the execution plan).

These functions contain the business rules and nothing else: no HTTP, no
database, no side effects. They take plain data in and return plain data out,
which is what makes them trivially unit-testable (no DB fixtures, no fake
requests) -- and testing the rules is exactly what the brief grades.

Relationship to the plan's signatures
--------------------------------------
The execution plan writes the core questions as ``can_user_approve(user,
request)`` and ``is_fully_approved(request)`` -- taking Django objects. Those
touch the database (``request.approvals``, ``request.status``), so they can't
run until Part A's models exist. We therefore split each into:

  * a PURE CORE here in logic.py that takes plain data (testable today), and
  * a thin ``request``/``user`` wrapper added in services.py once A's models
    land, which just extracts the data and calls the core.

Same behaviour and the same rule in one place -- we just keep it testable now,
which is the plan's own stated goal.
"""

from decimal import Decimal

from apps.accounts.models import Profile

# --- Roles (owned by A's Profile) vs levels (recorded on Approval) ---------
# Roles come straight from Profile so there is one source of truth: if A ever
# renames a role value, these rules follow automatically. Importing the model
# class only reads its constants -- no database access -- so this layer stays
# pure and its tests still run without a DB.
ROLE_MANAGER = Profile.MANAGER
ROLE_FINANCE = Profile.FINANCE

# Levels are what an Approval row records. Per the execution plan they are
# LOWERCASE and distinct from role names: a role is a capability, a level is
# the contribution an approver makes.
LEVEL_MANAGER = "manager"
LEVEL_FINANCE = "finance"

# The one place that maps "what you ARE" (role) to "what you CONTRIBUTE" (level).
# A role absent from this map cannot approve at all (employees, admins).
ROLE_TO_LEVEL = {
    ROLE_MANAGER: LEVEL_MANAGER,
    ROLE_FINANCE: LEVEL_FINANCE,
}

# KES. Up to and including this needs one manager; above also needs finance.
# Kept as Decimal so money never compares as a binary float.
MANAGER_LIMIT = Decimal("50000")

# --- Reason sentences returned when an approval is refused -----------------
# Named constants (not inline strings) so views, tests, and messages never
# drift apart. These are the exact user-facing sentences from the plan.
MSG_ROLE_CANNOT = "Your role cannot approve payments."
MSG_NOT_PENDING = "This request is not awaiting approval."
MSG_SELF_APPROVAL = "You cannot approve a request you created."
MSG_NOT_REQUIRED = "Your approval is not required for this request."
MSG_ALREADY_APPROVED = "This level has already approved."


def required_levels(amount):
    """Return the set of levels a payment of ``amount`` requires.

    - amount <= 50,000 -> {"manager"}
    - amount  > 50,000 -> {"manager", "finance"}

    This reads the CURRENT amount every time, which is the key design win: the
    tiered rule AND re-tiering after an amount change both fall out of it, with
    no "did it cross 50k" special case anywhere.
    """
    amount = Decimal(str(amount))
    if amount <= MANAGER_LIMIT:
        return {LEVEL_MANAGER}
    return {LEVEL_MANAGER, LEVEL_FINANCE}


def approver_level(role):
    """Map a user's role to the level they approve as, or None if they can't.

    Pure core of the plan's ``approver_level(user)``; the wrapper will pass
    ``user.profile.role``.
    """
    return ROLE_TO_LEVEL.get(role)


def evaluate_approval(*, role, is_requester, is_pending, amount, approved_levels):
    """Pure core of ``can_user_approve``: may this user approve right now?

    Returns ``(ok, reason)`` -- ``reason`` is ``None`` when allowed, else one of
    the MSG_* sentences. All inputs are plain data:

      - role:            the approver's Profile.role value.
      - is_requester:    True if the approver created this request.
      - is_pending:      True if the request is awaiting approval.
      - amount:          the request amount (decides required levels).
      - approved_levels: levels that already count as approved.

    Checks run in the plan's order; the FIRST failing one is reported.
    """
    level = approver_level(role)
    if level is None:                                   # 1. not an approver role
        return False, MSG_ROLE_CANNOT
    if not is_pending:                                  # 2. wrong state
        return False, MSG_NOT_PENDING
    if is_requester:                                    # 3. separation of duties
        return False, MSG_SELF_APPROVAL
    if level not in required_levels(amount):            # 4. tier not needed
        return False, MSG_NOT_REQUIRED
    if level in set(approved_levels):                   # 5. no double-approval
        return False, MSG_ALREADY_APPROVED
    return True, None


def is_fully_approved(amount, approved_levels):
    """True once every level ``amount`` requires has an approval that counts.

    Pure core of the plan's ``is_fully_approved(request)``; the wrapper will
    pass ``request.amount`` and the request's counting ``approved_levels``.
    Subset logic makes it order-independent and tolerant of extra levels.
    """
    return required_levels(amount).issubset(set(approved_levels))
