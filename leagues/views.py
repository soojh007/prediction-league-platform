import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import models
from django.db.models import Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AccountForm, CompetitionBrandingForm, FixtureSyncForm, JoinLeagueForm, LeagueSettingsForm, MatchForm, MatchResultForm, OrganiserEnquiryForm, PredictionForm, PrivateLeagueForm, SignUpForm, SupportedTeamForm, TeamForm
from .models import Competition, LeagueMembership, Match, Prediction, PrivateLeague, Team
from .services.sportmonks import SportMonksError, SportMonksSyncService


DEFAULT_LEAGUE_NAME = '2026-27 SPL Prediction League'
DEFAULT_LEAGUE_SLUG = 'spl2627'
TARGET_LEAGUE_SESSION_KEY = 'target_league_slug'
PLAYER_SESSION_AGE_SECONDS = 60 * 60 * 24 * 365 * 10
HOST_LEAGUE_SLUGS = {
    'spl2627': 'spl2627',
}
ADMIN_HOST_PREFIXES = {'admin', 'organiser', 'organizer'}


def is_organiser(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def get_host_prefix(request):
    host = request.get_host().split(':', 1)[0].lower()
    return host.split('.', 1)[0]


def is_admin_host(request):
    return get_host_prefix(request) in ADMIN_HOST_PREFIXES


def get_host_league_slug(request):
    return HOST_LEAGUE_SLUGS.get(get_host_prefix(request))


class LeagueLoginView(LoginView):
    template_name = 'registration/login.html'

    def dispatch(self, request, *args, **kwargs):
        if is_admin_host(request):
            return redirect('admin_login')

        league_slug = request.GET.get('league')
        if not league_slug:
            league_slug = get_host_league_slug(request)
        if league_slug:
            request.session[TARGET_LEAGUE_SESSION_KEY] = league_slug
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        target_league = get_target_league(self.request) or get_default_league()
        if target_league is not None:
            LeagueMembership.objects.get_or_create(
                league=target_league,
                user=self.request.user,
            )
            self.request.session.pop(TARGET_LEAGUE_SESSION_KEY, None)
            return target_league.get_absolute_url()

        first_membership = (
            LeagueMembership.objects
            .filter(user=self.request.user)
            .select_related('league')
            .order_by('-joined_at')
            .first()
        )
        if first_membership is not None:
            return first_membership.league.get_absolute_url()

        return super().get_success_url()

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session.set_expiry(PLAYER_SESSION_AGE_SECONDS)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'login_title': 'Player login',
            'login_eyebrow': 'Welcome back',
            'show_signup_link': True,
        })
        return context


class AdminLoginView(LoginView):
    template_name = 'registration/login.html'

    def get_success_url(self):
        return '/organiser/leagues/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'login_title': 'Organiser login',
            'login_eyebrow': 'Admin access',
            'show_signup_link': False,
        })
        return context


def home(request):
    if is_admin_host(request):
        if is_organiser(request.user):
            return redirect('organiser_leagues')
        return redirect('admin_login')

    target_league = get_host_league(request)

    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('dashboard')
        if target_league is not None:
            if LeagueMembership.objects.filter(league=target_league, user=request.user).exists():
                return redirect(target_league)
            return render_public_league_landing(request, target_league)
        return redirect('dashboard')

    if target_league is not None:
        return public_league_landing(request, target_league.slug)

    available_leagues = (
        PrivateLeague.objects
        .select_related('competition')
        .filter(competition__active=True)
        .order_by('competition__name', 'name')
    )
    return render(request, 'leagues/home.html', {
        'available_leagues': available_leagues,
    })


def public_league_landing(request, slug):
    league = get_object_or_404(
        PrivateLeague.objects.select_related('competition'),
        slug=slug,
        competition__active=True,
    )
    request.session[TARGET_LEAGUE_SESSION_KEY] = league.slug

    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('dashboard')
        if LeagueMembership.objects.filter(league=league, user=request.user).exists():
            return redirect(league)

    return render_public_league_landing(request, league)


def league_rules(request, slug):
    league = get_object_or_404(
        PrivateLeague.objects.select_related('competition'),
        slug=slug,
        competition__active=True,
    )
    is_league_member = (
        request.user.is_authenticated
        and not is_organiser(request.user)
        and LeagueMembership.objects.filter(league=league, user=request.user).exists()
    )
    return render(request, 'leagues/rules.html', {
        'league': league,
        'is_league_member': is_league_member,
    })


def render_public_league_landing(request, league):
    is_league_member = (
        request.user.is_authenticated
        and not is_organiser(request.user)
        and LeagueMembership.objects.filter(league=league, user=request.user).exists()
    )
    return render(request, 'leagues/home.html', {
        'league': league,
        'is_league_member': is_league_member,
    })


def organiser_enquiry(request):
    source_league = get_target_league(request)
    initial = {}
    if request.user.is_authenticated:
        initial['name'] = request.user.first_name or request.user.username
        initial['email'] = request.user.email
    if source_league is not None:
        initial['competition'] = source_league.competition.name
        if source_league.prediction_mode in dict(OrganiserEnquiryForm.base_fields['preferred_format'].choices):
            initial['preferred_format'] = source_league.prediction_mode

    if request.method == 'POST':
        form = OrganiserEnquiryForm(request.POST)
        if form.is_valid():
            enquiry = form.save(commit=False)
            enquiry.source_league = source_league
            enquiry.save()
            notify_organiser_enquiry(enquiry)
            messages.success(request, 'Thanks. Your organiser enquiry has been sent.')
            return redirect('home')
    else:
        form = OrganiserEnquiryForm(initial=initial)

    return render(request, 'leagues/organiser_enquiry.html', {
        'form': form,
        'source_league': source_league,
    })


def notify_organiser_enquiry(enquiry):
    body = '\n'.join([
        'New organiser enquiry',
        '',
        f'Name: {enquiry.name}',
        f'Email: {enquiry.email}',
        f'Competition: {enquiry.competition or "-"}',
        f'Preferred format: {enquiry.get_preferred_format_display()}',
        f'Estimated players: {enquiry.estimated_players or "-"}',
        f'Source league: {enquiry.source_league.name if enquiry.source_league else "-"}',
        '',
        'Message:',
        enquiry.message or '-',
    ])
    email = EmailMessage(
        subject=f'Prediction League organiser enquiry from {enquiry.name}',
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.CONTACT_EMAIL],
        reply_to=[enquiry.email],
    )
    try:
        email.send(fail_silently=False)
    except Exception:
        # Keep the saved database enquiry as the reliable fallback if SMTP is unavailable.
        pass


@login_required
def join_public_league(request, slug):
    if is_organiser(request.user):
        messages.error(request, 'Organiser accounts cannot join prediction leagues. Use a separate player account to play.')
        return redirect('dashboard')

    if request.method != 'POST':
        return redirect('public_league_landing', slug=slug)

    league = get_object_or_404(PrivateLeague, slug=slug, competition__active=True)
    LeagueMembership.objects.get_or_create(league=league, user=request.user)
    request.session.pop(TARGET_LEAGUE_SESSION_KEY, None)
    messages.success(request, f'Joined {league.name}.')
    return redirect(league)


def signup(request):
    if is_admin_host(request):
        return redirect('admin_login')

    target_league = get_target_league(request) or get_default_league()

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            if target_league is not None:
                LeagueMembership.objects.get_or_create(league=target_league, user=user)
            login(request, user)
            request.session.set_expiry(PLAYER_SESSION_AGE_SECONDS)
            request.session.pop(TARGET_LEAGUE_SESSION_KEY, None)
            if target_league is not None:
                return redirect(target_league)
            return redirect('dashboard')
    else:
        league_slug = request.GET.get('league')
        if league_slug:
            request.session[TARGET_LEAGUE_SESSION_KEY] = league_slug
            target_league = get_target_league(request) or target_league
        form = SignUpForm()
    return render(request, 'registration/signup.html', {
        'form': form,
        'target_league': target_league,
    })


def get_default_league():
    return (
        PrivateLeague.objects
        .select_related('competition')
        .filter(
            slug=DEFAULT_LEAGUE_SLUG,
            name=DEFAULT_LEAGUE_NAME,
            competition__name='Singapore Premier League',
            competition__active=True,
        )
        .order_by('id')
        .first()
    )


def get_host_league(request):
    league_slug = get_host_league_slug(request)
    if not league_slug:
        return None
    return (
        PrivateLeague.objects
        .select_related('competition')
        .filter(slug=league_slug, competition__active=True)
        .first()
    )


def get_target_league(request):
    league_slug = (
        request.GET.get('league')
        or request.POST.get('league')
        or request.session.get(TARGET_LEAGUE_SESSION_KEY)
        or get_host_league_slug(request)
    )
    if not league_slug:
        return None
    return (
        PrivateLeague.objects
        .select_related('competition')
        .filter(slug=league_slug, competition__active=True)
        .first()
    )


@login_required
def dashboard(request):
    can_create_league = request.user.is_staff or request.user.is_superuser
    memberships = LeagueMembership.objects.none()
    owned_leagues = PrivateLeague.objects.none()
    prediction_history = []
    accuracy = build_accuracy_summary(prediction_history)

    if can_create_league:
        owned_leagues = (
            PrivateLeague.objects
            .filter(owner=request.user)
            .select_related('competition')
            .order_by('-created_at')
        )
    else:
        memberships = (
            LeagueMembership.objects
            .filter(user=request.user)
            .filter(league__competition__active=True)
            .select_related('league', 'league__competition', 'supported_team')
            .order_by('-joined_at')
        )
        prediction_history = build_prediction_history(request.user)
        accuracy = build_accuracy_summary(prediction_history)
        dashboard_leaderboards = build_dashboard_leaderboards(memberships)
    if can_create_league:
        dashboard_leaderboards = None

    return render(request, 'leagues/dashboard.html', {
        'memberships': memberships,
        'owned_leagues': owned_leagues,
        'can_create_league': can_create_league,
        'join_form': JoinLeagueForm(),
        'prediction_history': prediction_history,
        'accuracy': accuracy,
        'dashboard_leaderboards': dashboard_leaderboards,
    })


@login_required
def organiser_leagues(request):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    leagues = (
        PrivateLeague.objects
        .filter(owner=request.user, competition__active=True)
        .select_related('competition')
        .annotate(
            player_count=models.Count('memberships', distinct=True),
            team_count=models.Count('competition__teams', distinct=True),
            match_count=models.Count('competition__matches', distinct=True),
            upcoming_match_count=models.Count(
                'competition__matches',
                filter=models.Q(competition__matches__status=Match.Status.UPCOMING),
                distinct=True,
            ),
            finished_match_count=models.Count(
                'competition__matches',
                filter=models.Q(competition__matches__status=Match.Status.FINISHED),
                distinct=True,
            ),
        )
        .order_by('competition__name', 'name')
    )

    return render(request, 'leagues/organiser_leagues.html', {
        'leagues': leagues,
    })


@login_required
def organiser_league_settings(request, pk):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    league = get_object_or_404(
        PrivateLeague.objects.select_related('competition', 'owner'),
        pk=pk,
        owner=request.user,
    )

    if request.method == 'POST':
        form = LeagueSettingsForm(request.POST, instance=league)
        branding_form = CompetitionBrandingForm(request.POST, instance=league.competition)
        if form.is_valid() and branding_form.is_valid():
            form.save()
            branding_form.save()
            messages.success(request, 'League settings saved.')
            return redirect('organiser_league_settings', pk=league.pk)
    else:
        form = LeagueSettingsForm(instance=league)
        branding_form = CompetitionBrandingForm(instance=league.competition)
    sync_form = FixtureSyncForm()

    members = (
        LeagueMembership.objects
        .filter(league=league)
        .select_related('user', 'supported_team')
        .order_by('user__username')
    )

    return render(request, 'leagues/organiser_league_settings.html', {
        'league': league,
        'form': form,
        'branding_form': branding_form,
        'sync_form': sync_form,
        'members': members,
    })


@login_required
def organiser_sync_fixtures(request, pk):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    league = get_owned_league_or_404(pk, request.user)
    if request.method != 'POST':
        return redirect('organiser_league_settings', pk=league.pk)

    form = FixtureSyncForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Check the sync dates and try again.')
        return redirect('organiser_league_settings', pk=league.pk)

    from_date = form.cleaned_data['from_date']
    to_date = form.cleaned_data['to_date']
    try:
        service = SportMonksSyncService()
        team_stats = None
        if form.cleaned_data['sync_teams']:
            team_stats = service.sync_teams(league.competition)
        stats = service.sync_fixtures(
            league.competition,
            from_date=from_date.isoformat() if from_date else None,
            to_date=to_date.isoformat() if to_date else None,
        )
    except (SportMonksError, ImproperlyConfigured) as error:
        messages.error(request, f'Fixture sync failed: {error}')
        return redirect('organiser_league_settings', pk=league.pk)

    recalculated = 0
    for match_id in stats['finished_match_ids']:
        recalculated += recalculate_match_points(
            league,
            Match.objects.get(pk=match_id, competition=league.competition),
        )

    summary = (
        f"Checked {stats['checked']}, created {stats['created']}, "
        f"updated {stats['updated']}, skipped {stats['skipped']}, "
        f"recalculated {recalculated} predictions"
    )
    if team_stats:
        summary = (
            f"Teams checked {team_stats['checked']}, created {team_stats['created']}, "
            f"updated {team_stats['updated']}. {summary}"
        )

    league.competition.last_fixture_sync_at = timezone.now()
    league.competition.last_fixture_sync_summary = summary[:255]
    league.competition.save(update_fields=['last_fixture_sync_at', 'last_fixture_sync_summary'])

    messages.success(request, f'Fixture sync complete. {summary}.')
    return redirect('organiser_league_settings', pk=league.pk)


@login_required
def organiser_export_data(request, pk, dataset):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    league = get_owned_league_or_404(pk, request.user)
    exporters = {
        'matches': export_matches_csv,
        'predictions': export_predictions_csv,
        'players': export_players_csv,
    }
    exporter = exporters.get(dataset)
    if exporter is None:
        raise Http404('Export not found')

    response = HttpResponse(content_type='text/csv')
    filename = f'{league.slug}-{dataset}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    exporter(writer, league)
    return response


@login_required
def organiser_teams(request, pk):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    league = get_owned_league_or_404(pk, request.user)
    teams = league.competition.teams.order_by('name')

    return render(request, 'leagues/organiser_teams.html', {
        'league': league,
        'teams': teams,
    })


@login_required
def organiser_team_create(request, pk):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    league = get_owned_league_or_404(pk, request.user)

    if request.method == 'POST':
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save(commit=False)
            team.competition = league.competition
            team.save()
            messages.success(request, 'Team added.')
            return redirect('organiser_teams', pk=league.pk)
    else:
        form = TeamForm()

    return render(request, 'leagues/organiser_team_form.html', {
        'league': league,
        'team': None,
        'form': form,
    })


@login_required
def organiser_team_edit(request, league_pk, team_pk):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    league = get_owned_league_or_404(league_pk, request.user)
    team = get_object_or_404(Team, pk=team_pk, competition=league.competition)

    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            messages.success(request, 'Team updated.')
            return redirect('organiser_teams', pk=league.pk)
    else:
        form = TeamForm(instance=team)

    return render(request, 'leagues/organiser_team_form.html', {
        'league': league,
        'team': team,
        'form': form,
    })


@login_required
def organiser_team_delete(request, league_pk, team_pk):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    league = get_owned_league_or_404(league_pk, request.user)
    team = get_object_or_404(Team, pk=team_pk, competition=league.competition)
    match_count = Match.objects.filter(models.Q(home_team=team) | models.Q(away_team=team)).count()
    member_count = LeagueMembership.objects.filter(league=league, supported_team=team).count()

    if request.method == 'POST':
        if match_count or member_count:
            messages.error(request, 'This team is already used, so it cannot be deleted. Edit it instead.')
            return redirect('organiser_teams', pk=league.pk)
        team.delete()
        messages.success(request, 'Team deleted.')
        return redirect('organiser_teams', pk=league.pk)

    return render(request, 'leagues/organiser_team_delete.html', {
        'league': league,
        'team': team,
        'match_count': match_count,
        'member_count': member_count,
    })


@login_required
def organiser_matches(request, pk):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    league = get_object_or_404(
        PrivateLeague.objects.select_related('competition', 'owner'),
        pk=pk,
        owner=request.user,
    )
    matches = (
        Match.objects
        .filter(competition=league.competition)
        .select_related('home_team', 'away_team')
        .order_by('kickoff_time')
    )

    return render(request, 'leagues/organiser_matches.html', {
        'league': league,
        'matches': matches,
    })


@login_required
def organiser_match_create(request, pk):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    league = get_object_or_404(
        PrivateLeague.objects.select_related('competition', 'owner'),
        pk=pk,
        owner=request.user,
    )

    if request.method == 'POST':
        form = MatchForm(request.POST, competition=league.competition)
        if form.is_valid():
            match = form.save(commit=False)
            match.competition = league.competition
            match.save()
            messages.success(request, 'Match added.')
            return redirect('organiser_matches', pk=league.pk)
    else:
        form = MatchForm(competition=league.competition)

    return render(request, 'leagues/organiser_match_form.html', {
        'league': league,
        'match': None,
        'form': form,
    })


@login_required
def organiser_match_edit(request, league_pk, match_pk):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    league = get_object_or_404(
        PrivateLeague.objects.select_related('competition', 'owner'),
        pk=league_pk,
        owner=request.user,
    )
    match = get_object_or_404(
        Match.objects.select_related('home_team', 'away_team'),
        pk=match_pk,
        competition=league.competition,
    )

    if request.method == 'POST':
        form = MatchForm(request.POST, instance=match, competition=league.competition)
        if form.is_valid():
            old_counts_towards_league = match.counts_towards_league
            form.save()
            if old_counts_towards_league != match.counts_towards_league:
                recalculate_match_points(league, match)
            messages.success(request, 'Match updated.')
            return redirect('organiser_matches', pk=league.pk)
    else:
        form = MatchForm(instance=match, competition=league.competition)

    return render(request, 'leagues/organiser_match_form.html', {
        'league': league,
        'match': match,
        'form': form,
    })


@login_required
def organiser_match_result(request, league_pk, match_pk):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    league = get_object_or_404(
        PrivateLeague.objects.select_related('competition', 'owner'),
        pk=league_pk,
        owner=request.user,
    )
    match = get_object_or_404(
        Match.objects.select_related('home_team', 'away_team'),
        pk=match_pk,
        competition=league.competition,
    )

    if request.method == 'POST':
        form = MatchResultForm(request.POST, instance=match)
        if form.is_valid():
            form.save()
            recalculated = recalculate_match_points(league, match)
            messages.success(request, f'Result saved. Recalculated {recalculated} predictions.')
            return redirect('organiser_matches', pk=league.pk)
    else:
        form = MatchResultForm(instance=match)

    return render(request, 'leagues/organiser_match_result.html', {
        'league': league,
        'match': match,
        'form': form,
    })


@login_required
def organiser_match_delete(request, league_pk, match_pk):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    league = get_object_or_404(
        PrivateLeague.objects.select_related('competition', 'owner'),
        pk=league_pk,
        owner=request.user,
    )
    match = get_object_or_404(
        Match.objects.select_related('home_team', 'away_team'),
        pk=match_pk,
        competition=league.competition,
    )
    prediction_count = Prediction.objects.filter(match=match).count()

    if request.method == 'POST':
        if prediction_count:
            messages.error(request, 'This match has predictions, so it cannot be deleted. Edit it instead.')
            return redirect('organiser_matches', pk=league.pk)
        match.delete()
        messages.success(request, 'Match deleted.')
        return redirect('organiser_matches', pk=league.pk)

    return render(request, 'leagues/organiser_match_delete.html', {
        'league': league,
        'match': match,
        'prediction_count': prediction_count,
    })


@login_required
def profile(request):
    if request.method == 'POST':
        account_form = AccountForm(request.POST, instance=request.user)
        if account_form.is_valid():
            account_form.save()
            messages.success(request, 'Profile updated.')
            return redirect('profile')
    else:
        account_form = AccountForm(instance=request.user)

    memberships = (
        LeagueMembership.objects
        .filter(user=request.user)
        .filter(league__competition__active=True)
        .select_related('league', 'league__competition', 'supported_team')
        .order_by('-joined_at')
    )

    return render(request, 'leagues/profile.html', {
        'account_form': account_form,
        'memberships': memberships,
    })


@login_required
def create_league(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'League creation is invite-only for now.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = PrivateLeagueForm(request.POST)
        if form.is_valid():
            league = form.save(commit=False)
            league.owner = request.user
            league.save()
            LeagueMembership.objects.get_or_create(
                league=league,
                user=request.user,
                defaults={'role': LeagueMembership.MemberRole.OWNER},
            )
            messages.success(request, 'League created.')
            return redirect(league)
    else:
        form = PrivateLeagueForm()
    return render(request, 'leagues/league_form.html', {'form': form})


@login_required
def join_league(request):
    if is_organiser(request.user):
        messages.error(request, 'Organiser accounts cannot join prediction leagues. Use a separate player account to play.')
        return redirect('dashboard')

    if request.method != 'POST':
        return redirect('dashboard')

    form = JoinLeagueForm(request.POST)
    if form.is_valid():
        league = get_object_or_404(PrivateLeague, join_code=form.cleaned_data['join_code'])
        LeagueMembership.objects.get_or_create(league=league, user=request.user)
        messages.success(request, f'Joined {league.name}.')
        return redirect(league)

    messages.error(request, 'Enter a valid invite code.')
    return redirect('dashboard')


@login_required
def league_detail(request, pk):
    if is_organiser(request.user):
        messages.error(request, 'Organiser accounts cannot play in prediction leagues. Use a separate player account to play.')
        return redirect('dashboard')

    league = get_object_or_404(
        PrivateLeague.objects.select_related('competition', 'owner'),
        pk=pk,
        competition__active=True,
    )
    membership = get_membership_or_404(league, request.user)
    matches = visible_matches_for(league, membership)
    predictions = {
        prediction.match_id: prediction
        for prediction in Prediction.objects.filter(user=request.user, league=league, match__in=matches)
    }
    has_predictions = Prediction.objects.filter(user=request.user, league=league).exists()
    leaderboard = build_leaderboard(league)
    league_status = build_league_status(request.user, league, matches, predictions, leaderboard)
    matchdays = build_matchdays(matches, open_match_limit=4)

    return render(request, 'leagues/league_detail.html', {
        'league': league,
        'membership': membership,
        'matches': matches,
        'matchdays': matchdays,
        'predictions': predictions,
        'has_predictions': has_predictions,
        'leaderboard': leaderboard,
        'league_status': league_status,
    })


@login_required
def leaderboard_detail(request, pk, user_pk):
    if is_organiser(request.user):
        messages.error(request, 'Organiser accounts cannot view player league pages. Use a separate player account to play.')
        return redirect('dashboard')

    league = get_object_or_404(PrivateLeague.objects.select_related('competition', 'owner'), pk=pk)
    get_membership_or_404(league, request.user)
    target_membership = get_object_or_404(
        LeagueMembership.objects
        .filter(user__is_staff=False, user__is_superuser=False)
        .select_related('user', 'supported_team'),
        league=league,
        user_id=user_pk,
    )
    is_own_detail = target_membership.user_id == request.user.id
    prediction_history = build_prediction_history(
        target_membership.user,
        league=league,
        include_unsettled=is_own_detail,
    )
    accuracy = build_accuracy_summary(prediction_history)
    total_points = sum(
        row['prediction'].points for row in prediction_history
        if row['counts_towards_league']
    )

    return render(request, 'leagues/leaderboard_detail.html', {
        'league': league,
        'membership': target_membership,
        'player': target_membership.user,
        'display_name': target_membership.user.first_name or target_membership.user.username,
        'prediction_history': prediction_history[:8],
        'accuracy': accuracy,
        'total_points': total_points,
        'is_own_detail': is_own_detail,
    })


@login_required
def choose_team(request, pk):
    if is_organiser(request.user):
        messages.error(request, 'Organiser accounts cannot choose a supported club. Use a separate player account to play.')
        return redirect('dashboard')

    league = get_object_or_404(PrivateLeague.objects.select_related('competition'), pk=pk)
    membership = get_membership_or_404(league, request.user)
    has_predictions = Prediction.objects.filter(user=request.user, league=league).exists()

    if has_predictions and request.method == 'POST':
        messages.error(request, 'Supported club is locked after your first prediction.')
        return redirect(league)

    if request.method == 'POST':
        form = SupportedTeamForm(request.POST, instance=membership, league=league)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supported club saved.')
            return redirect(league)
    else:
        form = SupportedTeamForm(instance=membership, league=league)

    return render(request, 'leagues/choose_team.html', {
        'league': league,
        'form': form,
        'has_predictions': has_predictions,
        'membership': membership,
    })


@login_required
def predict(request, league_pk, match_pk):
    if is_organiser(request.user):
        messages.error(request, 'Organiser accounts cannot submit predictions. Use a separate player account to play.')
        return redirect('dashboard')

    league = get_object_or_404(PrivateLeague.objects.select_related('competition'), pk=league_pk)
    membership = get_membership_or_404(league, request.user)
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team'), pk=match_pk)

    if match not in visible_matches_for(league, membership):
        raise Http404('Match not available for this league mode.')

    prediction = Prediction.objects.filter(user=request.user, league=league, match=match).first()
    is_locked = is_match_locked(match)
    if request.method == 'POST':
        if is_locked:
            messages.error(request, 'This match has kicked off, so predictions are locked.')
            return redirect(league)
        form = PredictionForm(request.POST, instance=prediction)
        if form.is_valid():
            prediction = form.save(commit=False)
            prediction.user = request.user
            prediction.league = league
            prediction.match = match
            prediction.save()
            messages.success(request, 'Prediction saved.')
            return redirect(league)
    else:
        form = PredictionForm(instance=prediction)

    match.deadline_label = match_deadline_label(match)
    match_info = build_match_info(league, match, request.user)

    return render(request, 'leagues/predict.html', {
        'league': league,
        'match': match,
        'form': form,
        'prediction': prediction,
        'is_locked': is_locked,
        'match_info': match_info,
    })


def get_membership_or_404(league, user):
    return get_object_or_404(
        LeagueMembership.objects.select_related('supported_team'),
        league=league,
        user=user,
    )


def get_owned_league_or_404(pk, user):
    return get_object_or_404(
        PrivateLeague.objects.select_related('competition', 'owner'),
        pk=pk,
        owner=user,
    )


def visible_matches_for(league, membership):
    matches = Match.objects.filter(competition=league.competition).select_related('home_team', 'away_team')

    if league.prediction_mode == PrivateLeague.PredictionMode.FEATURED:
        matches = matches.filter(featured=True)
    elif league.prediction_mode == PrivateLeague.PredictionMode.SUPPORTER:
        if membership.supported_team_id is None:
            return Match.objects.none()
        matches = matches.filter(
            models.Q(home_team=membership.supported_team) |
            models.Q(away_team=membership.supported_team)
        )

    return matches.order_by('kickoff_time')


def is_match_locked(match):
    return match.status == Match.Status.FINISHED or match.kickoff_time <= timezone.now()


def match_deadline_label(match):
    if match.status == Match.Status.FINISHED:
        return 'Finished'
    if is_match_locked(match):
        return 'Locked'

    remaining = match.kickoff_time - timezone.now()
    total_minutes = max(int(remaining.total_seconds() // 60), 0)
    if total_minutes < 60:
        return f'Locks in {total_minutes}m'

    total_hours = total_minutes // 60
    if total_hours < 24:
        minutes = total_minutes % 60
        if minutes:
            return f'Locks in {total_hours}h {minutes}m'
        return f'Locks in {total_hours}h'

    days = total_hours // 24
    return f'Locks in {days}d'


def build_match_info(league, match, user):
    prediction_summary = build_match_prediction_summary(league, match, user)
    return {
        'prediction_summary': prediction_summary,
        'home_form': build_team_recent_form(match.competition, match.home_team, match.kickoff_time),
        'away_form': build_team_recent_form(match.competition, match.away_team, match.kickoff_time),
    }


def build_match_prediction_summary(league, match, user):
    predictions = list(
        Prediction.objects
        .filter(league=league, match=match)
        .exclude(user=user)
        .select_related('user')
    )
    total = len(predictions)
    home_wins = sum(1 for prediction in predictions if prediction.predicted_home_score > prediction.predicted_away_score)
    draws = sum(1 for prediction in predictions if prediction.predicted_home_score == prediction.predicted_away_score)
    away_wins = max(total - home_wins - draws, 0)

    score_counts = {}
    for prediction in predictions:
        score = f'{prediction.predicted_home_score} - {prediction.predicted_away_score}'
        score_counts[score] = score_counts.get(score, 0) + 1

    popular_scores = [
        {
            'score': score,
            'count': count,
            'percent': round(count / total * 100) if total else 0,
        }
        for score, count in sorted(score_counts.items(), key=lambda item: (-item[1], item[0]))[:3]
    ]

    def percent(value):
        if not total:
            return 0
        return round(value / total * 100)

    return {
        'total': total,
        'home_percent': percent(home_wins),
        'draw_percent': percent(draws),
        'away_percent': percent(away_wins),
        'popular_scores': popular_scores,
    }


def build_team_recent_form(competition, team, before_time, limit=5):
    matches = (
        Match.objects
        .filter(
            competition=competition,
            status=Match.Status.FINISHED,
            kickoff_time__lt=before_time,
            home_score__isnull=False,
            away_score__isnull=False,
        )
        .filter(models.Q(home_team=team) | models.Q(away_team=team))
        .select_related('home_team', 'away_team')
        .order_by('-kickoff_time')[:limit]
    )

    rows = []
    wins = draws = losses = goals_for = goals_against = 0
    for completed_match in matches:
        is_home = completed_match.home_team_id == team.id
        team_score = completed_match.home_score if is_home else completed_match.away_score
        opponent_score = completed_match.away_score if is_home else completed_match.home_score
        opponent = completed_match.away_team if is_home else completed_match.home_team
        goals_for += team_score
        goals_against += opponent_score

        if team_score > opponent_score:
            result = 'W'
            wins += 1
        elif team_score == opponent_score:
            result = 'D'
            draws += 1
        else:
            result = 'L'
            losses += 1

        rows.append({
            'match': completed_match,
            'opponent': opponent,
            'result': result,
            'team_score': team_score,
            'opponent_score': opponent_score,
            'is_home': is_home,
        })

    total = len(rows)
    return {
        'team': team,
        'rows': rows,
        'total': total,
        'record': f'{wins}W {draws}D {losses}L',
        'goals_for': goals_for,
        'goals_against': goals_against,
        'goals_per_match': round(goals_for / total, 1) if total else 0,
        'conceded_per_match': round(goals_against / total, 1) if total else 0,
    }


def build_prediction_history(user, league=None, *, include_unsettled=True):
    predictions = (
        Prediction.objects
        .filter(user=user)
        .select_related('league', 'match', 'match__home_team', 'match__away_team')
        .order_by('-match__kickoff_time', '-updated_at')
    )
    if league is not None:
        predictions = predictions.filter(league=league)
    if not include_unsettled:
        predictions = predictions.filter(
            match__status=Match.Status.FINISHED,
            match__home_score__isnull=False,
            match__away_score__isnull=False,
        )

    rows = []
    for prediction in predictions:
        match = prediction.match
        has_result = match.home_score is not None and match.away_score is not None
        exact = has_result and prediction.predicted_home_score == match.home_score and prediction.predicted_away_score == match.away_score
        correct_result = False
        if has_result:
            actual_result = (match.home_score > match.away_score) - (match.home_score < match.away_score)
            predicted_result = (prediction.predicted_home_score > prediction.predicted_away_score) - (prediction.predicted_home_score < prediction.predicted_away_score)
            correct_result = predicted_result == actual_result

        rows.append({
            'prediction': prediction,
            'league': prediction.league,
            'match': match,
            'has_result': has_result,
            'exact': exact,
            'correct_result': correct_result,
            'counts_towards_league': match.counts_towards_league,
        })
    return rows


def build_accuracy_summary(prediction_history):
    finished_rows = [
        row for row in prediction_history
        if row['has_result'] and row['counts_towards_league']
    ]
    exact_scores = sum(1 for row in finished_rows if row['exact'])
    correct_results = sum(1 for row in finished_rows if row['correct_result'] and not row['exact'])
    other_predictions = max(len(finished_rows) - exact_scores - correct_results, 0)
    total = len(finished_rows)

    def percent(value):
        if not total:
            return 0
        return round(value / total * 100)

    return {
        'total': total,
        'exact_scores': exact_scores,
        'correct_results': correct_results,
        'other_predictions': other_predictions,
        'exact_percent': percent(exact_scores),
        'correct_percent': percent(correct_results),
        'other_percent': percent(other_predictions),
    }


def build_dashboard_leaderboards(memberships):
    memberships = list(memberships)
    if not memberships:
        return None

    league = memberships[0].league
    now = timezone.localtime()
    week_start = now - timedelta(days=now.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    return {
        'league': league,
        'week_start': week_start,
        'week_end': week_end,
        'weekly': build_leaderboard(league, from_time=week_start, to_time=week_end)[:5],
        'lifetime': build_leaderboard(league)[:5],
    }


def build_leaderboard(league, from_time=None, to_time=None):
    memberships = (
        LeagueMembership.objects
        .filter(league=league)
        .filter(user__is_staff=False, user__is_superuser=False)
        .select_related('user', 'supported_team')
    )
    rows = []
    for membership in memberships:
        predictions = Prediction.objects.filter(
            user=membership.user,
            league=league,
            match__counts_towards_league=True,
        )
        if from_time is not None:
            predictions = predictions.filter(match__kickoff_time__gte=from_time)
        if to_time is not None:
            predictions = predictions.filter(match__kickoff_time__lt=to_time)
        prediction_count = predictions.count()
        total_points = predictions.aggregate(total=Sum('points'))['total'] or 0
        exact_scores = predictions.filter(points=7).count()
        average = total_points / prediction_count if prediction_count else 0
        qualified = prediction_count >= league.minimum_predictions
        rows.append({
            'user': membership.user,
            'display_name': membership.user.first_name or membership.user.username,
            'supported_team': membership.supported_team,
            'prediction_count': prediction_count,
            'total_points': total_points,
            'exact_scores': exact_scores,
            'average': average,
            'qualified': qualified,
        })

    if league.ranking_mode == PrivateLeague.RankingMode.AVERAGE:
        rows.sort(key=lambda row: (row['qualified'], row['average'], row['exact_scores'], row['total_points']), reverse=True)
    else:
        rows.sort(key=lambda row: (row['total_points'], row['exact_scores'], row['average']), reverse=True)

    return rows


def build_league_status(user, league, matches, predictions, leaderboard):
    matches = list(matches)
    table_matches = [match for match in matches if match.counts_towards_league]
    table_predictions = {
        match_id: prediction
        for match_id, prediction in predictions.items()
        if prediction.match.counts_towards_league
    }
    open_playable_matches = [match for match in matches if not is_match_locked(match)]
    total_matches = len(table_matches)
    predicted_count = len(table_predictions)
    open_matches = len(open_playable_matches)
    finished_matches = sum(1 for match in matches if is_match_locked(match))
    unpredicted_open_matches = sum(
        1 for match in open_playable_matches
        if match.id not in predictions
    )
    completion_percent = round(predicted_count / total_matches * 100) if total_matches else 0
    next_prediction = next(
        (
            match for match in open_playable_matches
            if match.id not in predictions
        ),
        None,
    )

    rank = None
    total_points = 0
    leader_points = leaderboard[0]['total_points'] if leaderboard else 0
    for index, row in enumerate(leaderboard, start=1):
        if row['user'].id == user.id:
            rank = index
            total_points = row['total_points']
            break

    return {
        'rank': rank,
        'total_points': total_points,
        'points_behind': max(leader_points - total_points, 0),
        'predicted_count': predicted_count,
        'total_matches': total_matches,
        'open_matches': open_matches,
        'finished_matches': finished_matches,
        'unpredicted_open_matches': unpredicted_open_matches,
        'completion_percent': completion_percent,
        'next_prediction': next_prediction,
    }


def build_matchdays(matches, open_match_limit=None):
    grouped = []
    current_date = None
    current_group = None
    visible_open_matches = 0

    for match in matches:
        match.deadline_label = match_deadline_label(match)
        match.is_locked = is_match_locked(match)
        match_date = timezone.localtime(match.kickoff_time).date()
        if match_date != current_date:
            current_date = match_date
            current_group = {
                'date': match_date,
                'matches': [],
                'collapsed': False,
            }
            grouped.append(current_group)

        if open_match_limit is not None and not match.is_locked:
            if visible_open_matches >= open_match_limit:
                current_group['collapsed'] = True
            visible_open_matches += 1
        elif open_match_limit is not None and match.is_locked:
            current_group['collapsed'] = True

        current_group['matches'].append(match)

    return grouped


def recalculate_match_points(league, match):
    predictions = Prediction.objects.filter(league=league, match=match)
    count = 0
    for prediction in predictions:
        prediction.save()
        count += 1
    return count


def export_matches_csv(writer, league):
    writer.writerow([
        'match_id',
        'api_fixture_id',
        'match_day',
        'home_team',
        'away_team',
        'kickoff_time',
        'status',
        'home_score',
        'away_score',
        'venue',
        'featured',
        'counts_towards_league',
    ])
    for match in (
        Match.objects
        .filter(competition=league.competition)
        .select_related('home_team', 'away_team')
        .order_by('kickoff_time', 'id')
    ):
        writer.writerow([
            match.id,
            match.api_fixture_id or '',
            match.stage or '',
            match.home_team.name,
            match.away_team.name,
            timezone.localtime(match.kickoff_time).strftime('%Y-%m-%d %H:%M'),
            match.get_status_display(),
            '' if match.home_score is None else match.home_score,
            '' if match.away_score is None else match.away_score,
            match.venue,
            'yes' if match.featured else 'no',
            'yes' if match.counts_towards_league else 'no',
        ])


def export_predictions_csv(writer, league):
    writer.writerow([
        'prediction_id',
        'user_id',
        'username',
        'display_name',
        'email',
        'match_id',
        'api_fixture_id',
        'match_day',
        'home_team',
        'away_team',
        'kickoff_time',
        'predicted_home_score',
        'predicted_away_score',
        'actual_home_score',
        'actual_away_score',
        'status',
        'points',
        'counts_towards_league',
        'created_at',
        'updated_at',
    ])
    for prediction in (
        Prediction.objects
        .filter(league=league)
        .select_related('user', 'match', 'match__home_team', 'match__away_team')
        .order_by('match__kickoff_time', 'match_id', 'user__username')
    ):
        match = prediction.match
        writer.writerow([
            prediction.id,
            prediction.user_id,
            prediction.user.username,
            prediction.user.first_name or prediction.user.username,
            prediction.user.email,
            match.id,
            match.api_fixture_id or '',
            match.stage or '',
            match.home_team.name,
            match.away_team.name,
            timezone.localtime(match.kickoff_time).strftime('%Y-%m-%d %H:%M'),
            prediction.predicted_home_score,
            prediction.predicted_away_score,
            '' if match.home_score is None else match.home_score,
            '' if match.away_score is None else match.away_score,
            match.get_status_display(),
            prediction.points,
            'yes' if match.counts_towards_league else 'no',
            timezone.localtime(prediction.created_at).strftime('%Y-%m-%d %H:%M'),
            timezone.localtime(prediction.updated_at).strftime('%Y-%m-%d %H:%M'),
        ])


def export_players_csv(writer, league):
    writer.writerow([
        'user_id',
        'username',
        'display_name',
        'email',
        'role',
        'supported_team',
        'predictions',
        'exact_scores',
        'total_points',
        'joined_at',
    ])
    leaderboard_by_user = {
        row['user'].id: row
        for row in build_leaderboard(league)
    }
    for membership in (
        LeagueMembership.objects
        .filter(league=league)
        .select_related('user', 'supported_team')
        .order_by('user__username')
    ):
        row = leaderboard_by_user.get(membership.user_id, {})
        writer.writerow([
            membership.user_id,
            membership.user.username,
            membership.user.first_name or membership.user.username,
            membership.user.email,
            membership.get_role_display(),
            membership.supported_team.name if membership.supported_team else '',
            row.get('prediction_count', 0),
            row.get('exact_scores', 0),
            row.get('total_points', 0),
            timezone.localtime(membership.joined_at).strftime('%Y-%m-%d %H:%M'),
        ])

# Create your views here.
