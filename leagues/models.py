from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.text import slugify


class Competition(models.Model):
    class CompetitionType(models.TextChoices):
        API_LEAGUE = 'API_LEAGUE', 'API League'
        CUSTOM = 'CUSTOM', 'Custom League'

    name = models.CharField(max_length=120)
    competition_type = models.CharField(
        max_length=20,
        choices=CompetitionType.choices,
        default=CompetitionType.API_LEAGUE,
    )
    api_league_id = models.IntegerField(null=True, blank=True)
    api_season_id = models.IntegerField(null=True, blank=True)
    logo_url = models.URLField(blank=True)
    season = models.IntegerField(default=2026)
    country = models.CharField(max_length=100, blank=True)
    active = models.BooleanField(default=True)
    last_fixture_sync_at = models.DateTimeField(null=True, blank=True)
    last_fixture_sync_summary = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['api_league_id', 'season'],
                name='unique_api_competition_season',
                condition=models.Q(api_league_id__isnull=False),
            )
        ]

    def __str__(self):
        return f'{self.name} {self.season}'


class Team(models.Model):
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=120)
    short_name = models.CharField(max_length=20, blank=True)
    primary_color = models.CharField(max_length=20, default='#2368f6')
    api_team_id = models.IntegerField(null=True, blank=True)
    logo_url = models.URLField(blank=True)

    class Meta:
        ordering = ['name']
        unique_together = [('competition', 'name')]

    def __str__(self):
        return self.name


class PrivateLeague(models.Model):
    class PredictionMode(models.TextChoices):
        ALL = 'ALL', 'All matches'
        SUPPORTER = 'SUPPORTER', 'Supported club only'
        FEATURED = 'FEATURED', 'Featured matches only'

    class RankingMode(models.TextChoices):
        TOTAL = 'TOTAL', 'Total points'
        AVERAGE = 'AVERAGE', 'Average points'

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    join_code = models.CharField(max_length=16, unique=True, blank=True)
    landing_headline = models.CharField(max_length=160, blank=True)
    landing_intro = models.TextField(blank=True)
    landing_how_title = models.CharField(max_length=160, blank=True)
    landing_how_body = models.TextField(blank=True)
    landing_cta = models.CharField(max_length=80, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_prediction_leagues')
    competition = models.ForeignKey(Competition, on_delete=models.PROTECT, related_name='private_leagues')
    prediction_mode = models.CharField(
        max_length=20,
        choices=PredictionMode.choices,
        default=PredictionMode.SUPPORTER,
    )
    ranking_mode = models.CharField(
        max_length=20,
        choices=RankingMode.choices,
        default=RankingMode.TOTAL,
    )
    minimum_predictions = models.PositiveIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.join_code:
            self.join_code = get_random_string(8).upper()
        if not self.slug:
            base_slug = slugify(self.name)[:70] or 'league'
            slug = base_slug
            counter = 2
            while PrivateLeague.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                suffix = f'-{counter}'
                slug = f'{base_slug[:80 - len(suffix)]}{suffix}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('league_detail', args=[self.pk])

    def __str__(self):
        return self.name


class LeagueMembership(models.Model):
    class MemberRole(models.TextChoices):
        OWNER = 'OWNER', 'Owner'
        PLAYER = 'PLAYER', 'Player'

    league = models.ForeignKey(PrivateLeague, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='league_memberships')
    supported_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=20, choices=MemberRole.choices, default=MemberRole.PLAYER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('league', 'user')]

    def __str__(self):
        return f'{self.user.username} in {self.league.name}'


class LeagueNotice(models.Model):
    league = models.ForeignKey(PrivateLeague, on_delete=models.CASCADE, related_name='notices')
    title = models.CharField(max_length=120)
    message = models.TextField()
    active = models.BooleanField(default=True)
    pinned = models.BooleanField(default=False)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-pinned', '-created_at']

    def __str__(self):
        return f'{self.league.name}: {self.title}'


class Match(models.Model):
    class Status(models.TextChoices):
        UPCOMING = 'UPCOMING', 'Upcoming'
        FINISHED = 'FINISHED', 'Finished'

    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='matches')
    api_fixture_id = models.BigIntegerField(null=True, blank=True, unique=True)
    home_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name='away_matches')
    kickoff_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPCOMING)
    stage = models.CharField(max_length=80, blank=True)
    venue = models.CharField(max_length=120, blank=True)
    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    featured = models.BooleanField(default=False)
    counts_towards_league = models.BooleanField(default=True)

    class Meta:
        ordering = ['kickoff_time']
        indexes = [
            models.Index(fields=['competition', 'kickoff_time']),
            models.Index(fields=['featured']),
        ]

    def __str__(self):
        return f'{self.home_team} vs {self.away_team}'


class Prediction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='predictions')
    league = models.ForeignKey(PrivateLeague, on_delete=models.CASCADE, related_name='predictions')
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='predictions')
    predicted_home_score = models.PositiveSmallIntegerField()
    predicted_away_score = models.PositiveSmallIntegerField()
    points = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('user', 'league', 'match')]

    def calculate_points(self):
        if not self.match.counts_towards_league:
            return 0

        if self.match.home_score is None or self.match.away_score is None:
            return 0

        actual_home = self.match.home_score
        actual_away = self.match.away_score
        predicted_home = self.predicted_home_score
        predicted_away = self.predicted_away_score

        if predicted_home == actual_home and predicted_away == actual_away:
            return 7

        points = 0
        actual_result = (actual_home > actual_away) - (actual_home < actual_away)
        predicted_result = (predicted_home > predicted_away) - (predicted_home < predicted_away)

        if predicted_result == actual_result:
            points += 3
        if predicted_home - predicted_away == actual_home - actual_away:
            points += 1
        if predicted_home == actual_home:
            points += 1
        if predicted_away == actual_away:
            points += 1

        return points

    def save(self, *args, **kwargs):
        self.points = self.calculate_points()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user.username}: {self.league} - {self.match}'


class OrganiserEnquiry(models.Model):
    class PreferredFormat(models.TextChoices):
        SUPPORTER = 'SUPPORTER', 'Supported club only'
        ALL = 'ALL', 'All matches'
        FEATURED = 'FEATURED', 'Featured matches only'
        NOT_SURE = 'NOT_SURE', 'Not sure yet'

    name = models.CharField(max_length=120)
    email = models.EmailField()
    competition = models.CharField(max_length=160, blank=True)
    preferred_format = models.CharField(
        max_length=20,
        choices=PreferredFormat.choices,
        default=PreferredFormat.NOT_SURE,
    )
    estimated_players = models.PositiveIntegerField(null=True, blank=True)
    message = models.TextField(blank=True)
    source_league = models.ForeignKey(
        PrivateLeague,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='organiser_enquiries',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} - {self.competition or "Prediction league"}'
