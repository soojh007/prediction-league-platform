import json
import os
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from leagues.models import Competition, Match, PrivateLeague, Team


API_BASE_URL = 'https://v3.football.api-sports.io'
FINISHED_STATUSES = {'FT', 'AET', 'PEN'}


class ApiFootballError(Exception):
    pass


class ApiFootballClient:
    def __init__(self, api_key=None, base_url=API_BASE_URL):
        self.api_key = api_key or getattr(settings, 'FOOTBALL_API_KEY', '') or os.environ.get('FOOTBALL_API_KEY', '')
        self.base_url = base_url.rstrip('/')
        if not self.api_key:
            raise ImproperlyConfigured('FOOTBALL_API_KEY is not configured.')

    def get(self, path, **params):
        query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, '')})
        url = f'{self.base_url}{path}'
        if query:
            url = f'{url}?{query}'

        request = urllib.request.Request(
            url,
            headers={
                'x-apisports-key': self.api_key,
                'Accept': 'application/json',
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode('utf-8')
        except urllib.error.HTTPError as error:
            detail = error.read().decode('utf-8', errors='replace')
            raise ApiFootballError(f'API request failed with HTTP {error.code}: {detail}') from error
        except urllib.error.URLError as error:
            raise ApiFootballError(f'API request failed: {error.reason}') from error

        data = json.loads(body)
        errors = data.get('errors')
        if errors:
            raise ApiFootballError(f'API returned errors: {errors}')
        return data.get('response', [])

    def teams(self, api_league_id, season):
        return self.get('/teams', league=api_league_id, season=season)

    def fixtures(self, api_league_id, season, from_date=None, to_date=None, timezone_name='Asia/Singapore'):
        return self.get('/fixtures', **{
            'league': api_league_id,
            'season': season,
            'from': from_date,
            'to': to_date,
            'timezone': timezone_name,
        })


def resolve_competition(*, competition_id=None, private_league_id=None):
    if private_league_id:
        league = PrivateLeague.objects.select_related('competition').get(pk=private_league_id)
        return league.competition
    if competition_id:
        return Competition.objects.get(pk=competition_id)
    raise ValueError('Provide competition_id or private_league_id.')


class ApiFootballSyncService:
    def __init__(self, client=None):
        self.client = client or ApiFootballClient()

    def sync_teams(self, competition):
        self._require_api_competition(competition)
        stats = {'checked': 0, 'created': 0, 'updated': 0}

        for item in self.client.teams(competition.api_league_id, competition.season):
            stats['checked'] += 1
            team_data = item.get('team') or {}
            api_team_id = team_data.get('id')
            name = team_data.get('name')
            if not api_team_id or not name:
                continue

            defaults = {
                'name': name,
                'short_name': (team_data.get('code') or '')[:20],
                'logo_url': team_data.get('logo') or '',
            }
            team = Team.objects.filter(competition=competition, api_team_id=api_team_id).first()
            if team is None:
                team, created = Team.objects.update_or_create(
                    competition=competition,
                    name=name,
                    defaults={
                        **defaults,
                        'api_team_id': api_team_id,
                    },
                )
            else:
                created = False
                for field, value in defaults.items():
                    setattr(team, field, value)
                team.save()

            if created:
                stats['created'] += 1
            else:
                stats['updated'] += 1

        return stats

    def sync_fixtures(self, competition, *, from_date=None, to_date=None):
        self._require_api_competition(competition)
        stats = {
            'checked': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'match_ids': [],
            'finished_match_ids': [],
        }

        for item in self.client.fixtures(competition.api_league_id, competition.season, from_date, to_date):
            stats['checked'] += 1
            fixture = item.get('fixture') or {}
            teams = item.get('teams') or {}
            goals = item.get('goals') or {}
            league_data = item.get('league') or {}

            fixture_id = fixture.get('id')
            home = (teams.get('home') or {})
            away = (teams.get('away') or {})
            if not fixture_id or not home.get('id') or not away.get('id'):
                stats['skipped'] += 1
                continue

            home_team = self._upsert_fixture_team(competition, home)
            away_team = self._upsert_fixture_team(competition, away)
            kickoff = parse_datetime(fixture.get('date') or '')
            if kickoff is None:
                stats['skipped'] += 1
                continue
            if timezone.is_naive(kickoff):
                kickoff = timezone.make_aware(kickoff, timezone.get_current_timezone())

            status_short = ((fixture.get('status') or {}).get('short') or '').upper()
            is_finished = status_short in FINISHED_STATUSES
            venue = fixture.get('venue') or {}
            defaults = {
                'competition': competition,
                'home_team': home_team,
                'away_team': away_team,
                'kickoff_time': kickoff,
                'stage': league_data.get('round') or '',
                'venue': venue.get('name') or '',
                'status': Match.Status.FINISHED if is_finished else Match.Status.UPCOMING,
                'home_score': goals.get('home') if is_finished else None,
                'away_score': goals.get('away') if is_finished else None,
            }

            match, created = Match.objects.update_or_create(
                api_fixture_id=fixture_id,
                defaults=defaults,
            )
            stats['match_ids'].append(match.id)
            if is_finished:
                stats['finished_match_ids'].append(match.id)
            if created:
                stats['created'] += 1
            else:
                stats['updated'] += 1

        return stats

    def _upsert_fixture_team(self, competition, team_data):
        api_team_id = team_data.get('id')
        name = team_data.get('name')
        logo_url = team_data.get('logo') or ''

        team = Team.objects.filter(competition=competition, api_team_id=api_team_id).first()
        if team is not None:
            changed = False
            if name and team.name != name:
                team.name = name
                changed = True
            if logo_url and team.logo_url != logo_url:
                team.logo_url = logo_url
                changed = True
            if changed:
                team.save()
            return team

        team, _ = Team.objects.update_or_create(
            competition=competition,
            name=name,
            defaults={
                'api_team_id': api_team_id,
                'short_name': (team_data.get('code') or '')[:20],
                'logo_url': logo_url,
            },
        )
        return team

    def _require_api_competition(self, competition):
        if not competition.api_league_id:
            raise ApiFootballError(f'{competition.name} does not have an api_league_id.')
