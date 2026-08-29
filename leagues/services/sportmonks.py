import json
import os
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from leagues.models import Competition, Match, PrivateLeague, Team


API_BASE_URL = 'https://api.sportmonks.com/v3/football'
FINISHED_STATES = {
    'FT',
    'FULL_TIME',
    'FINISHED',
    'AET',
    'AFTER_EXTRA_TIME',
    'PEN',
    'AFTER_PENALTIES',
}


class SportMonksError(Exception):
    pass


class SportMonksClient:
    def __init__(self, api_token=None, base_url=API_BASE_URL):
        self.api_token = (
            api_token
            or getattr(settings, 'SPORTMONKS_API_TOKEN', '')
            or os.environ.get('SPORTMONKS_API_TOKEN', '')
        )
        self.base_url = base_url.rstrip('/')
        if not self.api_token:
            raise ImproperlyConfigured('SPORTMONKS_API_TOKEN is not configured.')

    def get(self, path, **params):
        params = {
            key: value
            for key, value in params.items()
            if value not in (None, '')
        }
        params['api_token'] = self.api_token

        results = []
        page = params.pop('page', None)
        while True:
            page_params = dict(params)
            if page:
                page_params['page'] = page

            query = urllib.parse.urlencode(page_params)
            url = f'{self.base_url}{path}?{query}'
            request = urllib.request.Request(url, headers={'Accept': 'application/json'})

            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = response.read().decode('utf-8')
            except urllib.error.HTTPError as error:
                detail = error.read().decode('utf-8', errors='replace')
                raise SportMonksError(f'SportMonks request failed with HTTP {error.code}: {detail}') from error
            except urllib.error.URLError as error:
                raise SportMonksError(f'SportMonks request failed: {error.reason}') from error

            data = json.loads(body)
            if data.get('errors'):
                raise SportMonksError(f"SportMonks returned errors: {data['errors']}")

            page_data = data.get('data') or []
            if isinstance(page_data, dict):
                page_data = [page_data]
            results.extend(page_data)

            pagination = data.get('pagination') or (data.get('meta') or {}).get('pagination') or {}
            if not pagination.get('has_more'):
                break
            page = pagination.get('next_page') or (pagination.get('current_page') or 1) + 1

        return results

    def teams(self, season_id):
        return self.get(f'/teams/seasons/{season_id}')

    def fixtures(self, season_id):
        schedule = self.get(f'/schedules/seasons/{season_id}')
        return self._extract_schedule_fixtures(schedule)

    def _extract_schedule_fixtures(self, schedule):
        fixtures = []

        def walk(node, stage=None, round_data=None):
            if isinstance(node, list):
                for item in node:
                    walk(item, stage=stage, round_data=round_data)
                return

            if not isinstance(node, dict):
                return

            next_stage = stage
            next_round = round_data
            if self._looks_like_stage(node):
                next_stage = self._lightweight_relation(node)
            if self._looks_like_round(node):
                next_round = self._lightweight_relation(node)

            if self._looks_like_fixture(node):
                fixture = dict(node)
                fixture.setdefault('stage', next_stage)
                fixture.setdefault('round', next_round)
                fixtures.append(fixture)
                return

            for value in node.values():
                walk(value, stage=next_stage, round_data=next_round)

        walk(schedule)
        return fixtures

    def _looks_like_fixture(self, node):
        return bool(node.get('id') and node.get('starting_at') and 'participants' in node)

    def _looks_like_stage(self, node):
        return 'rounds' in node and bool(node.get('name'))

    def _looks_like_round(self, node):
        return 'fixtures' in node and bool(node.get('name'))

    def _lightweight_relation(self, node):
        return {
            key: node.get(key)
            for key in ('id', 'name')
            if node.get(key) is not None
        }

    def league(self, league_id):
        league_data = self.get(f'/leagues/{league_id}', include='seasons')
        return league_data[0] if league_data else None

    def search_leagues(self, name):
        search_term = urllib.parse.quote(str(name))
        return self.get(f'/leagues/search/{search_term}', include='seasons')

    def season_id_for_league_data(self, league_data, season_year):
        seasons = league_data.get('seasons') or []
        matching_seasons = [
            season
            for season in seasons
            if self._season_matches_year(season, season_year)
        ]
        if not matching_seasons:
            raise SportMonksError(
                f"No SportMonks season matching {season_year} was found for {league_data.get('name', 'this league')}."
            )

        matching_seasons.sort(key=lambda season: str(season.get('starting_at') or season.get('name') or ''), reverse=True)
        return matching_seasons[0]['id']

    def _season_matches_year(self, season, season_year):
        year_text = str(season_year)
        if str(season.get('id')) == year_text:
            return True
        if year_text in str(season.get('name') or ''):
            return True
        if str(season.get('starting_at') or '').startswith(year_text):
            return True
        return False


def resolve_competition(*, competition_id=None, private_league_id=None):
    if private_league_id:
        league = PrivateLeague.objects.select_related('competition').get(pk=private_league_id)
        return league.competition
    if competition_id:
        return Competition.objects.get(pk=competition_id)
    raise ValueError('Provide competition_id or private_league_id.')


class SportMonksSyncService:
    def __init__(self, client=None):
        self.client = client or SportMonksClient()

    def sync_teams(self, competition):
        self._require_api_competition(competition)
        stats = {'checked': 0, 'created': 0, 'updated': 0}

        season_id = self._season_id(competition)
        for team_data in self.client.teams(season_id):
            stats['checked'] += 1
            api_team_id = team_data.get('id')
            name = team_data.get('name')
            if not api_team_id or not name:
                continue

            defaults = {
                'name': name,
                'short_name': (team_data.get('short_code') or team_data.get('code') or '')[:20],
                'logo_url': team_data.get('image_path') or team_data.get('logo_path') or '',
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
        season_id = self._season_id(competition)
        stats = {
            'checked': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'match_ids': [],
            'finished_match_ids': [],
        }

        for item in self.client.fixtures(season_id):
            kickoff = self._parse_kickoff(item.get('starting_at'))
            if not kickoff or not self._within_dates(kickoff, from_date, to_date):
                continue

            stats['checked'] += 1
            fixture_id = item.get('id')
            home_data, away_data = self._fixture_teams(item)
            if not fixture_id or not home_data or not away_data:
                stats['skipped'] += 1
                continue

            home_team = self._upsert_fixture_team(competition, home_data)
            away_team = self._upsert_fixture_team(competition, away_data)
            is_finished = self._is_finished(item)
            home_score, away_score = self._fixture_score(item, home_data, away_data)

            defaults = {
                'competition': competition,
                'home_team': home_team,
                'away_team': away_team,
                'kickoff_time': kickoff,
                'stage': self._stage_name(item),
                'venue': (item.get('venue') or {}).get('name') or '',
                'status': Match.Status.FINISHED if is_finished else Match.Status.UPCOMING,
                'home_score': home_score if is_finished else None,
                'away_score': away_score if is_finished else None,
            }

            match = Match.objects.filter(api_fixture_id=fixture_id).first()
            if match is not None:
                created = False
                self._update_api_linked_match(match=match, defaults=defaults, is_finished=is_finished)
            else:
                match = self._find_manual_match_for_api_fixture(
                    competition=competition,
                    home_team=home_team,
                    away_team=away_team,
                    kickoff=kickoff,
                )
                if match is not None:
                    created = False
                    self._attach_api_fixture_to_manual_match(
                        match=match,
                        fixture_id=fixture_id,
                        is_finished=is_finished,
                        home_score=home_score,
                        away_score=away_score,
                        stage=defaults['stage'],
                    )
                else:
                    match = Match.objects.create(
                        api_fixture_id=fixture_id,
                        **defaults,
                    )
                    created = True
            stats['match_ids'].append(match.id)
            if is_finished:
                stats['finished_match_ids'].append(match.id)
            if created:
                stats['created'] += 1
            else:
                stats['updated'] += 1

        return stats

    def _find_manual_match_for_api_fixture(self, *, competition, home_team, away_team, kickoff):
        api_match_date = timezone.localtime(kickoff).date()
        for match in Match.objects.filter(
            competition=competition,
            home_team=home_team,
            away_team=away_team,
            api_fixture_id__isnull=True,
        ):
            if timezone.localtime(match.kickoff_time).date() == api_match_date:
                return match
        return None

    def _update_api_linked_match(self, *, match, defaults, is_finished):
        update_fields = ['competition', 'home_team', 'away_team', 'status', 'home_score', 'away_score']
        match.competition = defaults['competition']
        match.home_team = defaults['home_team']
        match.away_team = defaults['away_team']
        match.status = defaults['status']
        match.home_score = defaults['home_score'] if is_finished else None
        match.away_score = defaults['away_score'] if is_finished else None

        if self._should_replace_stage(match.stage, defaults['stage']):
            match.stage = defaults['stage']
            update_fields.append('stage')

        if not match.venue and defaults['venue']:
            match.venue = defaults['venue']
            update_fields.append('venue')

        match.save(update_fields=update_fields)

    def _attach_api_fixture_to_manual_match(self, *, match, fixture_id, is_finished, home_score, away_score, stage):
        match.api_fixture_id = fixture_id
        if is_finished:
            match.status = Match.Status.FINISHED
            match.home_score = home_score
            match.away_score = away_score
        if self._should_replace_stage(match.stage, stage):
            match.stage = stage
        match.save(update_fields=['api_fixture_id', 'status', 'home_score', 'away_score', 'stage'])

    def _should_replace_stage(self, current_stage, api_stage):
        return bool(api_stage) and (not current_stage or current_stage == 'League')

    def _upsert_fixture_team(self, competition, team_data):
        api_team_id = team_data.get('id')
        name = team_data.get('name')
        logo_url = team_data.get('image_path') or team_data.get('logo_path') or ''

        team = Team.objects.filter(competition=competition, api_team_id=api_team_id).first()
        if team is not None:
            changed = False
            if logo_url and not team.logo_url:
                team.logo_url = logo_url
                changed = True
            if changed:
                team.save(update_fields=['logo_url'])
            return team

        team, _ = Team.objects.update_or_create(
            competition=competition,
            name=name,
            defaults={
                'api_team_id': api_team_id,
                'short_name': (team_data.get('short_code') or team_data.get('code') or '')[:20],
                'logo_url': logo_url,
            },
        )
        return team

    def _fixture_teams(self, item):
        home = None
        away = None
        for team in item.get('participants') or []:
            location = ((team.get('meta') or {}).get('location') or '').lower()
            if location == 'home':
                home = team
            elif location == 'away':
                away = team
        return home, away

    def _fixture_score(self, item, home_data, away_data):
        home_score = None
        away_score = None
        for score_item in item.get('scores') or []:
            if not self._is_preferred_score(score_item):
                continue
            score = score_item.get('score') or {}
            goals = score.get('goals')
            participant = (score.get('participant') or '').lower()
            participant_id = score_item.get('participant_id')

            if participant == 'home' or participant_id == home_data.get('id'):
                home_score = goals
            elif participant == 'away' or participant_id == away_data.get('id'):
                away_score = goals

        return home_score, away_score

    def _is_preferred_score(self, score_item):
        labels = self._labels(score_item)
        if not labels:
            return True
        return bool(labels & {'CURRENT', 'FT', 'FULLTIME', 'FULL_TIME', '2ND_HALF', '2ND_HALF_ONLY'})

    def _is_finished(self, item):
        state = item.get('state') or {}
        labels = self._labels(state)
        state_id = item.get('state_id')
        return bool(labels & FINISHED_STATES) or state_id in {5, 7, 8}

    def _stage_name(self, item):
        for key in ('round', 'stage', 'league'):
            value = item.get(key) or {}
            if value.get('name'):
                return value['name']
        return ''

    def _parse_kickoff(self, value):
        kickoff = parse_datetime(value or '')
        if kickoff is None:
            return None
        if timezone.is_naive(kickoff):
            kickoff = timezone.make_aware(kickoff, timezone.get_current_timezone())
        return kickoff

    def _within_dates(self, kickoff, from_date, to_date):
        kickoff_date = timezone.localtime(kickoff).date()
        if from_date and kickoff_date.isoformat() < from_date:
            return False
        if to_date and kickoff_date.isoformat() > to_date:
            return False
        return True

    def _labels(self, item):
        labels = set()
        for key in ('short_name', 'name', 'developer_name', 'description'):
            value = item.get(key)
            if value:
                labels.add(str(value).strip().upper().replace(' ', '_'))
        score_type = item.get('type') or {}
        for key in ('name', 'developer_name'):
            value = score_type.get(key)
            if value:
                labels.add(str(value).strip().upper().replace(' ', '_'))
        return labels

    def _require_api_competition(self, competition):
        if not competition.api_league_id:
            raise SportMonksError(f'{competition.name} does not have a SportMonks league ID.')

    def _season_id(self, competition):
        if competition.api_season_id:
            return competition.api_season_id

        league_data = self.client.league(competition.api_league_id)
        if league_data is None:
            league_data = self._find_league_by_name(competition)
        season_id = self.client.season_id_for_league_data(league_data, competition.season)
        competition.api_season_id = season_id
        competition.save(update_fields=['api_season_id'])
        return season_id

    def _find_league_by_name(self, competition):
        matches = []
        seen_ids = set()
        for search_term in self._league_search_terms(competition):
            for league in self.client.search_leagues(search_term):
                league_id = league.get('id')
                if league_id in seen_ids:
                    continue
                seen_ids.add(league_id)
                matches.append(league)

        candidates = [
            league
            for league in matches
            if self._league_matches_competition(league, competition)
        ]
        if not candidates:
            found_names = ', '.join(
                f"{league.get('name', 'Unnamed')} ({(league.get('country') or {}).get('name', 'unknown country')})"
                for league in matches[:8]
            ) or 'no search results'
            raise SportMonksError(
                f'SportMonks league {competition.api_league_id} was not found, '
                f'and no match for {competition.name} was found by search. '
                f'Found: {found_names}.'
            )

        league_data = candidates[0]
        if competition.api_league_id != league_data.get('id'):
            competition.api_league_id = league_data.get('id')
            competition.save(update_fields=['api_league_id'])
        return league_data

    def _league_search_terms(self, competition):
        terms = [competition.name]
        if competition.name == 'Singapore Premier League':
            terms.extend([
                'Singapore',
                'Premier League Singapore',
                'S League',
                'S.League',
                'SPL',
            ])
        if competition.country:
            terms.append(competition.country)
        return [term for index, term in enumerate(terms) if term and term not in terms[:index]]

    def _league_matches_competition(self, league_data, competition):
        league_name = str(league_data.get('name') or '').lower()
        competition_name = competition.name.lower()
        aliases = [competition_name]
        if competition.name == 'Singapore Premier League':
            aliases.extend([
                'singapore premier league',
                'premier league singapore',
                's league',
                's.league',
                'spl',
            ])

        if not any(alias in league_name or league_name in alias for alias in aliases):
            return False

        country = str(competition.country or '').lower()
        country_data = league_data.get('country') or {}
        country_name = str(country_data.get('name') or '').lower()
        if country and country_name and country not in country_name:
            return False
        return True
