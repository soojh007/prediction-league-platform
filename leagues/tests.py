from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Competition, LeagueMembership, Match, Prediction, PrivateLeague, Team


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
            predicted_home_score=2,
            predicted_away_score=1,
        )

        self.client.force_login(self.player)
        response = self.client.get(reverse('predict', args=[self.epl.pk, match.pk]))

        self.assertContains(response, 'How others see it')
        self.assertContains(response, 'Popular scores')
        self.assertContains(response, '2 - 1')
        self.assertContains(response, 'Recent form')
        self.assertContains(response, 'Main Stadium')
