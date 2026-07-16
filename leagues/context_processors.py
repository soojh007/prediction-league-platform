from .models import LeagueMembership


def player_navigation(request):
    if not request.user.is_authenticated:
        return {}

    if request.user.is_staff or request.user.is_superuser:
        return {}

    memberships = (
        LeagueMembership.objects
        .filter(user=request.user)
        .select_related('league')
        .order_by('-joined_at')
    )
    membership = memberships.first()

    return {
        'nav_primary_league': membership.league if membership else None,
        'nav_league_count': memberships.count(),
    }
