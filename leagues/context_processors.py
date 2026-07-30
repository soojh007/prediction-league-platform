from .models import LeagueMembership, PrivateLeague


HOST_LEAGUE_SLUGS = {
    'epl2627': 'epl2627',
    'spl2627': 'spl2627',
}


def get_host_league(request):
    host = request.get_host().split(':', 1)[0].lower()
    host_prefix = host.split('.', 1)[0]
    league_slug = HOST_LEAGUE_SLUGS.get(host_prefix)
    if not league_slug:
        return None

    return (
        PrivateLeague.objects
        .select_related('competition')
        .filter(slug=league_slug)
        .first()
    )


def player_navigation(request):
    host_league = get_host_league(request)

    if not request.user.is_authenticated:
        return {
            'nav_host_league': host_league,
        }

    if request.user.is_staff or request.user.is_superuser:
        return {
            'nav_host_league': host_league,
        }

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
        'nav_host_league': host_league,
    }


def analytics(request):
    from django.conf import settings

    return {
        'cloudflare_analytics_token': settings.CLOUDFLARE_ANALYTICS_TOKEN,
        'plausible_domain': settings.PLAUSIBLE_DOMAIN,
        'plausible_script_src': settings.PLAUSIBLE_SCRIPT_SRC,
    }
