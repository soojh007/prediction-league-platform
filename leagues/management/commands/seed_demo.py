from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from leagues.models import Competition, LeagueMembership, Match, PrivateLeague, Team


class Command(BaseCommand):
    help = 'Create demo competitions, teams, matches, and a sample league.'

    def handle(self, *args, **options):
        admin, _ = User.objects.get_or_create(username='admin', defaults={'email': 'admin@example.com'})
        admin.set_password('admin123')
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()

        epl = self.create_competition(
            name='Premier League',
            competition_type=Competition.CompetitionType.API_LEAGUE,
            api_league_id=None,
            season=2026,
            country='England',
            active=False,
            teams=[
                ('Arsenal', 'ARS', '#d9293f'),
                ('Aston Villa', 'AVL', '#6f1d46'),
                ('Chelsea', 'CHE', '#1b55b8'),
                ('Liverpool', 'LIV', '#c8102e'),
                ('Manchester City', 'MCI', '#6cabdd'),
                ('Manchester United', 'MUN', '#da291c'),
                ('Newcastle', 'NEW', '#1d1d1d'),
                ('Tottenham', 'TOT', '#10223f'),
            ],
        )

        spl = self.create_competition(
            name='Singapore Premier League',
            competition_type=Competition.CompetitionType.API_LEAGUE,
            api_league_id=1357,
            api_season_id=28091,
            season=2026,
            country='Singapore',
            teams=[
                ('Tampines Rovers', 'TAM', '#f38b00'),
                ('Lion City Sailors', 'LCS', '#2148b5'),
                ('FC Jurong', 'FCJ', '#ec2b35'),
                ('Hougang United', 'HOU', '#d62828'),
                ('Geylang International', 'GEY', '#188f5c'),
                ('Balestier Khalsa', 'BAL', '#c62838'),
                ('Young Lions', 'YLI', '#3f7fc1'),
                ('Tanjong Pagar', 'TPU', '#1f5aa6'),
            ],
        )

        self.create_matches(epl, [
            ('Liverpool', 'Arsenal', 1, '19:30', True),
            ('Chelsea', 'Manchester City', 2, '23:30', True),
            ('Manchester United', 'Liverpool', 8, '22:00', True),
            ('Tottenham', 'Newcastle', 9, '21:00', False),
            ('Arsenal', 'Chelsea', 15, '19:30', True),
            ('Aston Villa', 'Manchester United', 16, '23:30', False),
            ('Manchester City', 'Liverpool', 22, '22:00', True),
            ('Newcastle', 'Arsenal', 23, '21:00', False),
        ])

        self.create_matches(spl, [
            ('Tampines Rovers', 'Lion City Sailors', 1, '20:15', True),
            ('FC Jurong', 'Hougang United', 2, '18:00', False),
            ('Geylang International', 'Balestier Khalsa', 2, '20:15', False),
            ('Young Lions', 'Tanjong Pagar', 3, '18:00', True),
            ('Lion City Sailors', 'FC Jurong', 8, '20:15', True),
            ('Hougang United', 'Tampines Rovers', 9, '18:00', True),
            ('Balestier Khalsa', 'Young Lions', 9, '20:15', False),
            ('Tanjong Pagar', 'Geylang International', 10, '18:00', False),
        ])

        league, _ = PrivateLeague.objects.update_or_create(
            owner=admin,
            competition=epl,
            defaults={
                'name': '2026-27 EPL Prediction League',
                'slug': 'epl2627',
                'landing_headline': 'Back your club. Predict their matches. Climb the table.',
                'landing_intro': 'Join the 2026-27 EPL prediction league where you only need to predict the team you support. Simple enough for casual fans, competitive enough for bragging rights.',
                'landing_how_title': 'Pick one club and follow their season.',
                'landing_how_body': 'Instead of asking every player to predict every match, this league keeps it fair and light: choose your supported club, predict their fixtures, and compete on a leaderboard built around the same scoring rules.',
                'landing_cta': 'Join the 2026-27 EPL League',
                'prediction_mode': PrivateLeague.PredictionMode.SUPPORTER,
                'ranking_mode': PrivateLeague.RankingMode.TOTAL,
                'minimum_predictions': 5,
            },
        )
        LeagueMembership.objects.get_or_create(
            league=league,
            user=admin,
            defaults={
                'role': LeagueMembership.MemberRole.OWNER,
                'supported_team': Team.objects.filter(competition=epl, name='Liverpool').first(),
            },
        )

        spl_league, _ = PrivateLeague.objects.update_or_create(
            owner=admin,
            competition=spl,
            defaults={
                'name': '2026-27 SPL Prediction League',
                'slug': 'spl2627',
                'landing_headline': 'Predict every SPL match. Own the local table.',
                'landing_intro': 'Join the 2026-27 SPL prediction league for fans who want the full matchday challenge. Predict every fixture, track your points, and see who reads the league best.',
                'landing_how_title': 'Every fixture counts.',
                'landing_how_body': 'This league uses the full-fixture model: everyone predicts the same SPL matches, so the leaderboard is direct, simple, and easy to compare.',
                'landing_cta': 'Join the 2026-27 SPL League',
                'prediction_mode': PrivateLeague.PredictionMode.ALL,
                'ranking_mode': PrivateLeague.RankingMode.TOTAL,
                'minimum_predictions': 5,
            },
        )
        LeagueMembership.objects.get_or_create(
            league=spl_league,
            user=admin,
            defaults={
                'role': LeagueMembership.MemberRole.OWNER,
                'supported_team': None,
            },
        )
        LeagueMembership.objects.filter(league=spl_league).update(supported_team=None)

        self.stdout.write(self.style.SUCCESS('Demo data ready. Login with admin / admin123.'))

    def create_competition(self, name, competition_type, season, country, teams, api_league_id=None, api_season_id=None, active=True):
        competition, _ = Competition.objects.update_or_create(
            name=name,
            season=season,
            defaults={
                'competition_type': competition_type,
                'api_league_id': api_league_id,
                'api_season_id': api_season_id,
                'country': country,
                'active': active,
            },
        )
        for team_name, short_name, color in teams:
            Team.objects.update_or_create(
                competition=competition,
                name=team_name,
                defaults={'short_name': short_name, 'primary_color': color},
            )
        return competition

    def create_matches(self, competition, fixtures):
        teams = {team.name: team for team in competition.teams.all()}
        base = timezone.localtime().replace(hour=19, minute=30, second=0, microsecond=0)
        for home, away, days, time_text, featured in fixtures:
            hour, minute = [int(part) for part in time_text.split(':')]
            kickoff = (base + timedelta(days=days)).replace(hour=hour, minute=minute)
            Match.objects.update_or_create(
                competition=competition,
                home_team=teams[home],
                away_team=teams[away],
                defaults={
                    'kickoff_time': kickoff,
                    'stage': 'League',
                    'featured': featured,
                    'venue': 'Main Stadium',
                },
            )
