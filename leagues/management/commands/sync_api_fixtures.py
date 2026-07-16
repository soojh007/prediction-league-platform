from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ImproperlyConfigured

from leagues.services.api_football import ApiFootballError, ApiFootballSyncService, resolve_competition


class Command(BaseCommand):
    help = 'Sync fixtures for an API-backed competition.'

    def add_arguments(self, parser):
        parser.add_argument('--competition-id', type=int, help='Competition row ID to sync.')
        parser.add_argument('--private-league-id', type=int, help='Private league ID whose competition should be synced.')
        parser.add_argument('--from', dest='from_date', help='Start date in YYYY-MM-DD format.')
        parser.add_argument('--to', dest='to_date', help='End date in YYYY-MM-DD format.')
        parser.add_argument(
            '--with-teams',
            action='store_true',
            help='Sync teams before syncing fixtures.',
        )

    def handle(self, *args, **options):
        try:
            competition = resolve_competition(
                competition_id=options.get('competition_id'),
                private_league_id=options.get('private_league_id'),
            )
            service = ApiFootballSyncService()
            team_stats = None
            if options['with_teams']:
                team_stats = service.sync_teams(competition)
            stats = service.sync_fixtures(
                competition,
                from_date=options.get('from_date'),
                to_date=options.get('to_date'),
            )
        except (ApiFootballError, ImproperlyConfigured, ValueError) as error:
            raise CommandError(str(error)) from error

        if team_stats is not None:
            self.stdout.write(
                f"Team sync checked {team_stats['checked']}, created {team_stats['created']}, updated {team_stats['updated']}."
            )
        self.stdout.write(self.style.SUCCESS(
            f'Fixture sync complete for {competition.name} {competition.season}. '
            f"Checked: {stats['checked']}. Created: {stats['created']}. "
            f"Updated: {stats['updated']}. Skipped: {stats['skipped']}."
        ))
