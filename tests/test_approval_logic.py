"""Unit tests for the pure approval rules (apps/approvals/logic.py).

SimpleTestCase -> no database is created (the logic is pure). Case numbers and
scenarios come straight from the execution plan's test matrix (section 9), so
these tests double as executable documentation. Matrix rows that need Part A's
models (rejection reason storage, amount-change supersession, audit rows) are
covered later at the service layer.
"""

from decimal import Decimal

from django.test import SimpleTestCase

from apps.approvals import logic
from apps.approvals.logic import LEVEL_MANAGER as M, LEVEL_FINANCE as F
from apps.accounts.models import Profile

EMPLOYEE = Profile.EMPLOYEE
MANAGER = Profile.MANAGER
FINANCE = Profile.FINANCE
ADMIN = Profile.ADMIN


class RequiredLevelsTests(SimpleTestCase):
    """Tiering rule (matrix rows 1-4): <=50k -> manager; >50k -> manager+finance."""

    def test_24500_needs_one_manager(self):
        self.assertEqual(logic.required_levels(24_500), {M})

    def test_42000_needs_one_manager(self):
        self.assertEqual(logic.required_levels(42_000), {M})

    def test_67000_needs_manager_and_finance(self):
        self.assertEqual(logic.required_levels(67_000), {M, F})

    def test_148000_needs_manager_and_finance(self):
        self.assertEqual(logic.required_levels(148_000), {M, F})

    def test_exactly_50000_is_manager_only(self):
        self.assertEqual(logic.required_levels(50_000), {M})

    def test_just_over_50000_needs_finance_too(self):
        self.assertEqual(logic.required_levels(Decimal("50000.01")), {M, F})

    def test_accepts_decimal_and_string_amounts(self):
        self.assertEqual(logic.required_levels(Decimal("24500")), {M})
        self.assertEqual(logic.required_levels("67000"), {M, F})


class ApproverLevelTests(SimpleTestCase):
    """Role -> level mapping: only manager/finance roles contribute a level."""

    def test_manager_role_maps_to_manager_level(self):
        self.assertEqual(logic.approver_level(MANAGER), M)

    def test_finance_role_maps_to_finance_level(self):
        self.assertEqual(logic.approver_level(FINANCE), F)

    def test_employee_and_admin_have_no_level(self):
        self.assertIsNone(logic.approver_level(EMPLOYEE))
        self.assertIsNone(logic.approver_level(ADMIN))


class EvaluateApprovalTests(SimpleTestCase):
    """may-this-user-approve core (matrix rows 5, 6, 7, 10, 11 + tier/allow)."""

    def _approve(self, **overrides):
        """A valid manager-approves-a-small-request call, tweak per test."""
        base = dict(
            role=MANAGER,
            is_requester=False,
            is_pending=True,
            amount=24_500,
            approved_levels=set(),
        )
        base.update(overrides)
        return logic.evaluate_approval(**base)

    # --- Allowed paths ---
    def test_manager_may_approve_small_request(self):
        self.assertEqual(self._approve(), (True, None))

    def test_finance_may_approve_large_request_after_manager(self):
        ok, reason = self._approve(role=FINANCE, amount=67_000, approved_levels={M})
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_finance_may_approve_large_request_before_manager(self):
        # The two >50k approvals are separate and order-independent.
        ok, _ = self._approve(role=FINANCE, amount=148_000)
        self.assertTrue(ok)

    # --- Row 6 & 7: RBAC ---
    def test_employee_cannot_approve(self):
        self.assertEqual(self._approve(role=EMPLOYEE), (False, logic.MSG_ROLE_CANNOT))

    def test_admin_cannot_approve(self):
        self.assertEqual(self._approve(role=ADMIN), (False, logic.MSG_ROLE_CANNOT))

    # --- Row 11: must be awaiting approval ---
    def test_cannot_approve_when_not_pending(self):
        self.assertEqual(
            self._approve(is_pending=False), (False, logic.MSG_NOT_PENDING)
        )

    # --- Row 5: separation of duties ---
    def test_cannot_approve_own_request(self):
        self.assertEqual(
            self._approve(is_requester=True), (False, logic.MSG_SELF_APPROVAL)
        )

    # --- Tier correctness: finance can't stand in for a manager-only request ---
    def test_finance_not_required_on_small_request(self):
        self.assertEqual(
            self._approve(role=FINANCE), (False, logic.MSG_NOT_REQUIRED)
        )

    # --- Row 10: no double-approval by the same level ---
    def test_same_level_cannot_approve_twice(self):
        self.assertEqual(
            self._approve(amount=67_000, approved_levels={M}),
            (False, logic.MSG_ALREADY_APPROVED),
        )

    # --- Check order: role is tested before state/self-approval ---
    def test_role_is_checked_before_everything_else(self):
        ok, reason = self._approve(role=EMPLOYEE, is_requester=True, is_pending=False)
        self.assertEqual(reason, logic.MSG_ROLE_CANNOT)


class IsFullyApprovedTests(SimpleTestCase):
    """is-it-fully-approved core (matrix rows 2, 3, 4)."""

    def test_row2_small_request_complete_with_one_manager(self):
        self.assertTrue(logic.is_fully_approved(24_500, {M}))

    def test_small_request_incomplete_with_no_approvals(self):
        self.assertFalse(logic.is_fully_approved(24_500, set()))

    def test_row3_large_request_incomplete_with_manager_only(self):
        self.assertFalse(logic.is_fully_approved(148_000, {M}))

    def test_row4_large_request_complete_with_both(self):
        self.assertTrue(logic.is_fully_approved(148_000, {M, F}))

    def test_order_independent(self):
        self.assertTrue(logic.is_fully_approved(67_000, {F, M}))

    def test_extra_levels_tolerated(self):
        self.assertTrue(logic.is_fully_approved(24_500, {M, F}))
