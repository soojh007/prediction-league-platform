from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from tempfile import NamedTemporaryFile

from .models import Competition, LeagueMembership, Match, OrganiserEnquiry, Prediction, PrivateLeague, Team
from .services.sportmonks import SportMonksSyncService


class LeagueJoinFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='password123', is_staff=True)
        self.player = User.objects.create_user(username='player', password='password123')

        self.epl = self.create_league('2026-27 EPL Prediction League', 'epl2627', 'Premier League')
        self.spl = self.create_league('2026-27 SPL Prediction League', 'spl2627', 'Singapore Premier League')

    def create_league(self, name, slug, competition_name):
        competition = Competition.objects.create(name=competition_name)
        return PrivateLeague.objects.create(
            name=name,
            slug=slug,
            owner=self.owner,
            competition=competition,
        )

    def test_viewing_another_public_league_does_not_auto_join(self):
        LeagueMembership.objects.create(league=self.epl, user=self.player)
        self.client.force_login(self.player)

        response = self.client.get(reverse('public_league_landing', args=[self.spl.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(LeagueMembership.objects.filter(league=self.epl, user=self.player).exists())
        self.assertFalse(LeagueMembership.objects.filter(league=self.spl, user=self.player).exists())

    def test_public_league_join_button_joins_only_that_league(self):
        LeagueMembership.objects.create(league=self.epl, user=self.player)
        self.client.force_login(self.player)

        response = self.client.post(reverse('join_public_league', args=[self.spl.slug]))

        self.assertRedirects(response, self.spl.get_absolute_url())
        self.assertEqual(LeagueMembership.objects.filter(user=self.player).count(), 2)
        self.assertTrue(LeagueMembership.objects.filter(league=self.spl, user=self.player).exists())

    def test_rules_page_is_public(self):
        response = self.client.get(reverse('league_rules', args=[self.epl.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '7 points per match')
        self.assertContains(response, self.epl.name)

    def test_rules_page_links_back_to_joined_league(self):
        LeagueMembership.objects.create(league=self.epl, user=self.player)
        self.client.force_login(self.player)

        response = self.client.get(reverse('league_rules', args=[self.epl.slug]))

        self.assertContains(response, 'Back to league')

    def test_organiser_dashboard_counts_league_setup(self):
        home = Team.objects.create(competition=self.epl.competition, name='Arsenal')
        away = Team.objects.create(competition=self.epl.competition, name='Chelsea')
        Match.objects.create(
            competition=self.epl.competition,
            home_team=home,
            away_team=away,
            kickoff_time=timezone.now(),
            status=Match.Status.UPCOMING,
        )
        Match.objects.create(
            competition=self.epl.competition,
            home_team=away,
            away_team=home,
            kickoff_time=timezone.now(),
            status=Match.Status.FINISHED,
            home_score=1,
            away_score=0,
        )
        LeagueMembership.objects.create(league=self.epl, user=self.player)

        self.client.force_login(self.owner)
        response = self.client.get(reverse('organiser_leagues'))

        league = next(item for item in response.context['leagues'] if item.pk == self.epl.pk)
        self.assertEqual(league.player_count, 1)
        self.assertEqual(league.team_count, 2)
        self.assertEqual(league.match_count, 2)
        self.assertEqual(league.upcoming_match_count, 1)
        self.assertEqual(league.finished_match_count, 1)

    def test_league_detail_shows_match_availability_overview(self):
        self.epl.prediction_mode = PrivateLeague.PredictionMode.ALL
        self.epl.save()
        home = Team.objects.create(competition=self.epl.competition, name='Arsenal')
        away = Team.objects.create(competition=self.epl.competition, name='Chelsea')
        for days in (1, 2):
            Match.objects.create(
                competition=self.epl.competition,
                home_team=home,
                away_team=away,
                kickoff_time=timezone.now() + timezone.timedelta(days=days),
                status=Match.Status.UPCOMING,
            )
        Match.objects.create(
            competition=self.epl.competition,
            home_team=away,
            away_team=home,
            kickoff_time=timezone.now() - timezone.timedelta(days=1),
            status=Match.Status.FINISHED,
            home_score=1,
            away_score=0,
        )
        LeagueMembership.objects.create(league=self.epl, user=self.player)

        self.client.force_login(self.player)
        response = self.client.get(self.epl.get_absolute_url())

        self.assertContains(response, 'Open matches')
        self.assertContains(response, 'Settled matches')
        self.assertContains(response, 'To predict')
        self.assertContains(response, '<strong>2</strong>', html=True)
        self.assertContains(response, '<strong>1</strong>', html=True)

    def test_predictions_lock_after_kickoff(self):
        self.epl.prediction_mode = PrivateLeague.PredictionMode.ALL
        self.epl.save()
        home = Team.objects.create(competition=self.epl.competition, name='Arsenal')
        away = Team.objects.create(competition=self.epl.competition, name='Chelsea')
        match = Match.objects.create(
            competition=self.epl.competition,
            home_team=home,
            away_team=away,
            kickoff_time=timezone.now() - timezone.timedelta(minutes=1),
            status=Match.Status.UPCOMING,
        )
        LeagueMembership.objects.create(league=self.epl, user=self.player)

        self.client.force_login(self.player)
        response = self.client.post(
            reverse('predict', args=[self.epl.pk, match.pk]),
            {'predicted_home_score': 1, 'predicted_away_score': 0},
        )

        self.assertRedirects(response, self.epl.get_absolute_url())
        self.assertFalse(Prediction.objects.filter(user=self.player, match=match).exists())

    def test_league_detail_shows_deadline_label(self):
        self.epl.prediction_mode = PrivateLeague.PredictionMode.ALL
        self.epl.save()
        home = Team.objects.create(competition=self.epl.competition, name='Arsenal')
        away = Team.objects.create(competition=self.epl.competition, name='Chelsea')
        Match.objects.create(
            competition=self.epl.competition,
            home_team=home,
            away_team=away,
            kickoff_time=timezone.now() + timezone.timedelta(hours=2),
            status=Match.Status.UPCOMING,
        )
        LeagueMembership.objects.create(league=self.epl, user=self.player)

        self.client.force_login(self.player)
        response = self.client.get(self.epl.get_absolute_url())

        self.assertContains(response, 'Locks in')

    def test_prediction_page_shows_match_context(self):
        self.epl.prediction_mode = PrivateLeague.PredictionMode.ALL
        self.epl.save()
        home = Team.objects.create(competition=self.epl.competition, name='Arsenal')
        away = Team.objects.create(competition=self.epl.competition, name='Chelsea')
        rival = Team.objects.create(competition=self.epl.competition, name='Liverpool')
        player_two = User.objects.create_user(username='player-two', password='password123')
        match = Match.objects.create(
            competition=self.epl.competition,
            home_team=home,
            away_team=away,
            kickoff_time=timezone.now() + timezone.timedelta(days=1),
            venue='Main Stadium',
            status=Match.Status.UPCOMING,
        )
        Match.objects.create(
            competition=self.epl.competition,
            home_team=home,
            away_team=rival,
            kickoff_time=timezone.now() - timezone.timedelta(days=3),
            status=Match.Status.FINISHED,
            home_score=2,
            away_score=0,
        )
        Match.objects.create(
            competition=self.epl.competition,
            home_team=rival,
            away_team=away,
            kickoff_time=timezone.now() - timezone.timedelta(days=2),
            status=Match.Status.FINISHED,
            home_score=1,
            away_score=1,
        )
        LeagueMembership.objects.create(league=self.epl, user=self.player)
        LeagueMembership.objects.create(league=self.epl, user=player_two)
        Prediction.objects.create(
            user=player_two,
            league=self.epl,
            match=match,
            predicted_home_score=4,
            predicted_away_score=3,
        )

        self.client.force_login(self.player)
        response = self.client.get(reverse('predict', args=[self.epl.pk, match.pk]))

        self.assertContains(response, 'How others see it')
        self.assertContains(response, 'Popular scores')
        self.assertContains(response, '4 - 3')
        self.assertContains(response, 'Recent form')
        self.assertContains(response, 'Main Stadium')

    def test_leaderboard_rows_link_to_player_detail(self):
        self.epl.prediction_mode = PrivateLeague.PredictionMode.ALL
        self.epl.save()
        home = Team.objects.create(competition=self.epl.competition, name='Arsenal')
        away = Team.objects.create(competition=self.epl.competition, name='Chelsea')
        match = Match.objects.create(
            competition=self.epl.competition,
            home_team=home,
            away_team=away,
            kickoff_time=timezone.now() - timezone.timedelta(days=1),
            status=Match.Status.FINISHED,
            home_score=2,
            away_score=1,
        )
        LeagueMembership.objects.create(league=self.epl, user=self.player)
        Prediction.objects.create(
            user=self.player,
            league=self.epl,
            match=match,
            predicted_home_score=2,
            predicted_away_score=1,
        )

        self.client.force_login(self.player)
        response = self.client.get(self.epl.get_absolute_url())

        detail_url = reverse('leaderboard_detail', args=[self.epl.pk, self.player.pk])
        self.assertContains(response, f'href="{detail_url}"')

    def test_leaderboard_detail_shows_player_breakdown(self):
        self.epl.prediction_mode = PrivateLeague.PredictionMode.SUPPORTER
        self.epl.save()
        home = Team.objects.create(competition=self.epl.competition, name='Arsenal')
        away = Team.objects.create(competition=self.epl.competition, name='Chelsea')
        exact_match = Match.objects.create(
            competition=self.epl.competition,
            home_team=home,
            away_team=away,
            kickoff_time=timezone.now() - timezone.timedelta(days=2),
            status=Match.Status.FINISHED,
            home_score=2,
            away_score=1,
        )
        result_match = Match.objects.create(
            competition=self.epl.competition,
            home_team=home,
            away_team=away,
            kickoff_time=timezone.now() - timezone.timedelta(days=1),
            status=Match.Status.FINISHED,
            home_score=3,
            away_score=1,
        )
        LeagueMembership.objects.create(league=self.epl, user=self.player, supported_team=home)
        Prediction.objects.create(
            user=self.player,
            league=self.epl,
            match=exact_match,
            predicted_home_score=2,
            predicted_away_score=1,
        )
        Prediction.objects.create(
            user=self.player,
            league=self.epl,
            match=result_match,
            predicted_home_score=2,
            predicted_away_score=0,
        )

        self.client.force_login(self.player)
        response = self.client.get(reverse('leaderboard_detail', args=[self.epl.pk, self.player.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Exact scores')
        self.assertContains(response, '<strong>1</strong>', html=True)
        self.assertContains(response, 'Correct results')
        self.assertContains(response, 'Arsenal')
        self.assertContains(response, 'How player picked')
        self.assertContains(response, '2 - 1')

    def test_leaderboard_detail_hides_other_players_unsettled_predictions(self):
        self.epl.prediction_mode = PrivateLeague.PredictionMode.ALL
        self.epl.save()
        viewer = User.objects.create_user(username='viewer', password='password123')
        home = Team.objects.create(competition=self.epl.competition, name='Arsenal')
        away = Team.objects.create(competition=self.epl.competition, name='Chelsea')
        upcoming_match = Match.objects.create(
            competition=self.epl.competition,
            home_team=home,
            away_team=away,
            kickoff_time=timezone.now() + timezone.timedelta(days=1),
            status=Match.Status.UPCOMING,
        )
        finished_match = Match.objects.create(
            competition=self.epl.competition,
            home_team=away,
            away_team=home,
            kickoff_time=timezone.now() - timezone.timedelta(days=1),
            status=Match.Status.FINISHED,
            home_score=1,
            away_score=0,
        )
        LeagueMembership.objects.create(league=self.epl, user=self.player)
        LeagueMembership.objects.create(league=self.epl, user=viewer)
        Prediction.objects.create(
            user=self.player,
            league=self.epl,
            match=upcoming_match,
            predicted_home_score=4,
            predicted_away_score=3,
        )
        Prediction.objects.create(
            user=self.player,
            league=self.epl,
            match=finished_match,
            predicted_home_score=1,
            predicted_away_score=0,
        )

        self.client.force_login(viewer)
        response = self.client.get(reverse('leaderboard_detail', args=[self.epl.pk, self.player.pk]))

        self.assertContains(response, '1 - 0')
        self.assertNotContains(response, '4 - 3')
        self.assertNotContains(response, 'Pending')

        self.client.force_login(self.player)
        response = self.client.get(reverse('leaderboard_detail', args=[self.epl.pk, self.player.pk]))

        self.assertContains(response, '4 - 3')
        self.assertContains(response, 'Pending')

    def test_one_off_matches_do_not_count_towards_leaderboard(self):
        self.epl.prediction_mode = PrivateLeague.PredictionMode.ALL
        self.epl.save()
        home = Team.objects.create(competition=self.epl.competition, name='Arsenal')
        away = Team.objects.create(competition=self.epl.competition, name='Chelsea')
        league_match = Match.objects.create(
            competition=self.epl.competition,
            home_team=home,
            away_team=away,
            kickoff_time=timezone.now() - timezone.timedelta(days=2),
            status=Match.Status.FINISHED,
            home_score=2,
            away_score=1,
        )
        one_off_match = Match.objects.create(
            competition=self.epl.competition,
            home_team=away,
            away_team=home,
            kickoff_time=timezone.now() - timezone.timedelta(days=1),
            status=Match.Status.FINISHED,
            home_score=3,
            away_score=0,
            counts_towards_league=False,
        )
        LeagueMembership.objects.create(league=self.epl, user=self.player)
        Prediction.objects.create(
            user=self.player,
            league=self.epl,
            match=league_match,
            predicted_home_score=2,
            predicted_away_score=1,
        )
        bonus_prediction = Prediction.objects.create(
            user=self.player,
            league=self.epl,
            match=one_off_match,
            predicted_home_score=3,
            predicted_away_score=0,
        )

        self.assertEqual(bonus_prediction.points, 0)

        self.client.force_login(self.player)
        response = self.client.get(self.epl.get_absolute_url())

        self.assertContains(response, 'Does not count')
        self.assertContains(response, '<strong class="leaderboard-points">7</strong>', html=True)
        self.assertContains(response, '1 predictions · 1 exact')

    def test_one_off_matches_can_be_next_prediction(self):
        self.epl.prediction_mode = PrivateLeague.PredictionMode.ALL
        self.epl.save()
        home = Team.objects.create(competition=self.epl.competition, name='Arsenal')
        away = Team.objects.create(competition=self.epl.competition, name='Chelsea')
        Match.objects.create(
            competition=self.epl.competition,
            home_team=home,
            away_team=away,
            kickoff_time=timezone.now() + timezone.timedelta(days=1),
            status=Match.Status.UPCOMING,
            counts_towards_league=False,
        )
        LeagueMembership.objects.create(league=self.epl, user=self.player)

        self.client.force_login(self.player)
        response = self.client.get(self.epl.get_absolute_url())

        self.assertContains(response, 'Next prediction')
        self.assertContains(response, 'Arsenal')
        self.assertContains(response, 'Predict now')

    def test_landing_page_links_to_organiser_enquiry_form(self):
        response = self.client.get(reverse('home'))

        self.assertContains(response, reverse('organiser_enquiry'))
        self.assertContains(response, 'Enquire')

    @override_settings(
        CLOUDFLARE_ANALYTICS_TOKEN='cf-token',
        PLAUSIBLE_DOMAIN='predictionleague.site',
        PLAUSIBLE_SCRIPT_SRC='https://plausible.io/js/script.js',
    )
    def test_landing_page_can_include_analytics_snippets(self):
        response = self.client.get(reverse('home'))

        self.assertContains(response, 'static.cloudflareinsights.com/beacon.min.js')
        self.assertContains(response, 'data-cf-beacon=\'{"token": "cf-token"}\'')
        self.assertContains(response, 'data-domain="predictionleague.site"')
        self.assertContains(response, 'https://plausible.io/js/script.js')

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        CONTACT_EMAIL='hello@predictionleague.site',
        DEFAULT_FROM_EMAIL='Prediction League <no-reply@predictionleague.site>',
    )
    def test_organiser_enquiry_form_saves_enquiry_and_sends_email(self):
        response = self.client.post(reverse('organiser_enquiry'), {
            'name': 'Soo',
            'email': 'soo@example.com',
            'competition': 'Premier League',
            'preferred_format': 'SUPPORTER',
            'estimated_players': 24,
            'message': 'I want to run a league for friends.',
        })

        self.assertRedirects(response, reverse('home'))
        enquiry = OrganiserEnquiry.objects.get()
        self.assertEqual(enquiry.email, 'soo@example.com')
        self.assertEqual(enquiry.preferred_format, 'SUPPORTER')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['hello@predictionleague.site'])
        self.assertEqual(mail.outbox[0].reply_to, ['soo@example.com'])

    def test_import_custom_fixtures_upserts_csv_rows(self):
        self.spl.prediction_mode = PrivateLeague.PredictionMode.ALL
        self.spl.save()
        home = Team.objects.create(competition=self.spl.competition, name='Lion City Sailors')
        away = Team.objects.create(competition=self.spl.competition, name='Tampines Rovers')

        with NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as csv_file:
            csv_file.write(
                'kickoff_time,home_team,away_team,venue,stage,featured,counts_towards_league\n'
                '2026-09-11T19:30:00+08:00,Lion City Sailors,Tampines Rovers,Jalan Besar Stadium,League,false,true\n'
            )
            csv_path = csv_file.name

        call_command('import_custom_fixtures', csv_path, private_league_slug=self.spl.slug)
        call_command('import_custom_fixtures', csv_path, private_league_slug=self.spl.slug)

        matches = Match.objects.filter(competition=self.spl.competition, home_team=home, away_team=away)
        self.assertEqual(matches.count(), 1)
        self.assertEqual(matches.get().venue, 'Jalan Besar Stadium')

    def test_sportmonks_sync_imports_teams_and_fixtures(self):
        self.epl.competition.api_league_id = 23690
        self.epl.competition.save(update_fields=['api_league_id'])

        class FakeSportMonksClient:
            def season_id_for_league(self, league_id, season_year):
                self.league_id = league_id
                self.season_year = season_year
                return 23690

            def teams(self, season_id):
                self.season_id = season_id
                return [
                    {'id': 1, 'name': 'Arsenal', 'short_code': 'ARS', 'image_path': 'https://example.com/ars.png'},
                    {'id': 2, 'name': 'Chelsea', 'short_code': 'CHE', 'image_path': 'https://example.com/che.png'},
                ]

            def fixtures(self, season_id):
                self.fixture_season_id = season_id
                return [
                    {
                        'id': 9001,
                        'starting_at': '2026-08-16 19:30:00',
                        'state_id': 5,
                        'state': {'short_name': 'FT', 'name': 'Finished'},
                        'round': {'name': 'Round 1'},
                        'venue': {'name': 'Emirates Stadium'},
                        'participants': [
                            {
                                'id': 1,
                                'name': 'Arsenal',
                                'short_code': 'ARS',
                                'image_path': 'https://example.com/ars.png',
                                'meta': {'location': 'home'},
                            },
                            {
                                'id': 2,
                                'name': 'Chelsea',
                                'short_code': 'CHE',
                                'image_path': 'https://example.com/che.png',
                                'meta': {'location': 'away'},
                            },
                        ],
                        'scores': [
                            {
                                'participant_id': 1,
                                'description': 'CURRENT',
                                'score': {'goals': 2, 'participant': 'home'},
                            },
                            {
                                'participant_id': 2,
                                'description': 'CURRENT',
                                'score': {'goals': 1, 'participant': 'away'},
                            },
                        ],
                    },
                ]

        client = FakeSportMonksClient()
        service = SportMonksSyncService(client=client)

        team_stats = service.sync_teams(self.epl.competition)
        fixture_stats = service.sync_fixtures(self.epl.competition, from_date='2026-08-01', to_date='2026-08-31')

        self.assertEqual(client.league_id, 23690)
        self.assertEqual(client.season_year, 2026)
        self.assertEqual(client.season_id, 23690)
        self.assertEqual(client.fixture_season_id, 23690)
        self.assertEqual(team_stats, {'checked': 2, 'created': 2, 'updated': 0})
        self.assertEqual(fixture_stats['checked'], 1)
        self.assertEqual(fixture_stats['created'], 1)

        match = Match.objects.get(api_fixture_id=9001)
        self.assertEqual(match.home_team.name, 'Arsenal')
        self.assertEqual(match.away_team.name, 'Chelsea')
        self.assertEqual(match.status, Match.Status.FINISHED)
        self.assertEqual(match.home_score, 2)
        self.assertEqual(match.away_score, 1)
        self.assertEqual(match.stage, 'Round 1')
        self.assertEqual(match.venue, 'Emirates Stadium')
