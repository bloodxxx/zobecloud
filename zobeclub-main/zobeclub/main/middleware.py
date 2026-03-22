from django.utils import timezone


class LastSeenMiddleware:
    """Updates UserProfile.last_seen on every authenticated request (throttled to once per minute)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            try:
                profile = request.user.profile
                from datetime import timedelta
                # Only write to DB at most once per minute to avoid excessive queries
                if profile.last_seen is None or profile.last_seen < timezone.now() - timedelta(minutes=1):
                    profile.last_seen = timezone.now()
                    profile.save(update_fields=['last_seen'])
            except Exception:
                pass
        return response
