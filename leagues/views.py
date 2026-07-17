from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import AccountForm, CompetitionBrandingForm, FixtureSyncForm, JoinLeagueForm, LeagueSettingsForm, MatchForm, MatchResultForm, PredictionForm, PrivateLeagueForm, SignUpForm, SupportedTeamForm, TeamForm
from .models import Competition, LeagueMembership, Match, Prediction, PrivateLeague, Team
from .services.api_football import ApiFootballError, ApiFootballSyncService


DEFAULT_LEAGUE_NAME = '2026-27 EPL Prediction League'
DEFAULT_LEAGUE_SLUG = 'epl2627'
TARGET_LEAGUE_SESSION_KEY = 'target_league_slug'
PLAYER_SESSION_AGE_SECONDS = 60 * 60 * 24 * 365 * 10
HOST_LEAGUE_SLUGS = {
    'epl2627': 'epl2627',
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
            LeagueMembership.objects.get_or_create(
                league=target_league,
                user=request.user,
            )
            return redirect(target_league)
        return redirect('dashboard')

    if target_league is not None:
        return public_league_landing(request, target_league.slug)

    available_leagues = (
        PrivateLeague.objects
        .select_related('competition')
        .order_by('competition__name', 'name')
    )
    return render(request, 'leagues/home.html', {
        'available_leagues': available_leagues,
    })


def public_league_landing(request, slug):
    league = get_object_or_404(
        PrivateLeague.objects.select_related('competition'),
        slug=slug,
    )
    request.session[TARGET_LEAGUE_SESSION_KEY] = league.slug

    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('dashboard')
        LeagueMembership.objects.get_or_create(league=league, user=request.user)
        return redirect(league)

    return render(request, 'leagues/home.html', {
        'league': league,
    })


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
        .filter(slug=DEFAULT_LEAGUE_SLUG, name=DEFAULT_LEAGUE_NAME, competition__name='Premier League')
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
        .filter(slug=league_slug)
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
        .filter(slug=league_slug)
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
            .select_related('league', 'league__competition', 'supported_team')
            .order_by('-joined_at')
        )
        prediction_history = build_prediction_history(request.user)
        accuracy = build_accuracy_summary(prediction_history)

    return render(request, 'leagues/dashboard.html', {
        'memberships': memberships,
        'owned_leagues': owned_leagues,
        'can_create_league': can_create_league,
        'join_form': JoinLeagueForm(),
        'prediction_history': prediction_history,
        'accuracy': accuracy,
    })


@login_required
def organiser_leagues(request):
    if not is_organiser(request.user):
        messages.error(request, 'Organiser access is invite-only for now.')
        return redirect('dashboard')

    leagues = (
        PrivateLeague.objects
        .filter(owner=request.user)
        .select_related('competition')
        .prefetch_related('memberships')
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
        service = ApiFootballSyncService()
        team_stats = None
        if form.cleaned_data['sync_teams']:
            team_stats = service.sync_teams(league.competition)
        stats = service.sync_fixtures(
            league.competition,
            from_date=from_date.isoformat() if from_date else None,
            to_date=to_date.isoformat() if to_date else None,
        )
    except (ApiFootballError, ImproperlyConfigured) as error:
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
            form.save()
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

    league = get_object_or_404(PrivateLeague.objects.select_related('competition', 'owner'), pk=pk)
    membership = get_membership_or_404(league, request.user)
    matches = visible_matches_for(league, membership)
    predictions = {
        prediction.match_id: prediction
        for prediction in Prediction.objects.filter(user=request.user, league=league, match__in=matches)
    }
    has_predictions = Prediction.objects.filter(user=request.user, league=league).exists()
    leaderboard = build_leaderboard(league)
    league_status = build_league_status(request.user, league, matches, predictions, leaderboard)
    matchdays = build_matchdays(matches)

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
    is_locked = match.status == Match.Status.FINISHED
    if request.method == 'POST':
        if is_locked:
            messages.error(request, 'This match is finished, so predictions are locked.')
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

    return render(request, 'leagues/predict.html', {
        'league': league,
        'match': match,
        'form': form,
        'prediction': prediction,
        'is_locked': is_locked,
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


def build_prediction_history(user):
    predictions = (
        Prediction.objects
        .filter(user=user)
        .select_related('league', 'match', 'match__home_team', 'match__away_team')
        .order_by('-match__kickoff_time', '-updated_at')
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
        })
    return rows


def build_accuracy_summary(prediction_history):
    finished_rows = [row for row in prediction_history if row['has_result']]
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


def build_leaderboard(league):
    memberships = (
        LeagueMembership.objects
        .filter(league=league)
        .filter(user__is_staff=False, user__is_superuser=False)
        .select_related('user', 'supported_team')
    )
    rows = []
    for membership in memberships:
        predictions = Prediction.objects.filter(user=membership.user, league=league)
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
    total_matches = len(matches)
    predicted_count = len(predictions)
    completion_percent = round(predicted_count / total_matches * 100) if total_matches else 0
    next_prediction = next(
        (
            match for match in matches
            if match.status != Match.Status.FINISHED and match.id not in predictions
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
        'completion_percent': completion_percent,
        'next_prediction': next_prediction,
    }


def build_matchdays(matches):
    grouped = []
    current_date = None
    current_group = None

    for match in matches:
        match_date = timezone.localtime(match.kickoff_time).date()
        if match_date != current_date:
            current_date = match_date
            current_group = {
                'date': match_date,
                'matches': [],
            }
            grouped.append(current_group)
        current_group['matches'].append(match)

    return grouped


def recalculate_match_points(league, match):
    predictions = Prediction.objects.filter(league=league, match=match)
    count = 0
    for prediction in predictions:
        prediction.save()
        count += 1
    return count

# Create your views here.
