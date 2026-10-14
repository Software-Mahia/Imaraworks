"""Who can see which payment requests. TEMPORARY copy.

This repeats visible_requests() from PR #2 (apps/payment_requests/views.py,
Part A), which isn't merged yet. Once #2 merges, delete this file and import
visible_requests from there, so there is one visibility rule, not two.

The rule (Part A's, see API.md "Who sees what"):
  - MANAGER, FINANCE: every request
  - EMPLOYEE:         only their own
  - ADMIN, no role:   none
"""

from apps.accounts.models import Profile
from apps.payment_requests.models import PaymentRequest

CAN_SEE_ALL = (Profile.MANAGER, Profile.FINANCE)


def visible_requests(user):
    profile = getattr(user, "profile", None)
    role = profile.role if profile else None
    qs = PaymentRequest.objects.all()
    if role in CAN_SEE_ALL:
        return qs
    if role == Profile.EMPLOYEE:
        return qs.filter(requester=user)
    return qs.none()
