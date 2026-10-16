from typing import Optional

from django.contrib.auth.models import User


def get_role(user: User) -> Optional[str]:
    """Return the user's role string, or None if they have no profile."""
    profile = getattr(user, 'profile', None)
    return profile.role if profile else None