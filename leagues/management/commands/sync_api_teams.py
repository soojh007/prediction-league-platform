from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ImproperlyConfigured

from leagues.services.sportmonks import SportMonksError, SportMonksSyncService, resolve_competition


class Command(BaseCommand):
    help = 'Sync teams and badges for an API-backed competition.'

    def add_arguments(self, parser):
        parser.add_argument('--competition-id', type=int, help='Competition row ID to sync.')
        parser.add_argument('--private-league-id', type=int, help='Private league ID whose competition should be synced.')

    def handle(self, *args, **options):
        try:
            competition = resolve_competition(
                competition_id=options.get('competition_id'),
                private_league_id=options.get('private_league_id'),
            )
            stats = SportMonksSyncService().sync_teams(competition)
        except (SportMonksError, ImproperlyConfigured, ValueError) as error:
            raise CommandError(str(error)) from error

        self.stdout.write(self.style.SUCCESS(
            f'Team sync complete for {competition.name} {competition.season}. '
            f"Checked: {stats['checked']}. Created: {stats['created']}. Updated: {stats['updated']}."
        ))
