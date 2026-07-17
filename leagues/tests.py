from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Competition, LeagueMembership, PrivateLeague


class LeagueJoinFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='password123')
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
