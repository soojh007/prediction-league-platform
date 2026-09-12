from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Sync a rolling window of recent API fixtures.'

    def add_arguments(self, parser):
        parser.add_argument('--competition-id', type=int, help='Competition row ID to sync.')
        parser.add_argument('--private-league-id', type=int, help='Private league ID whose competition should be synced.')
        parser.add_argument('--days-back', type=int, default=1, help='Days before today to include.')
        parser.add_argument('--days-ahead', type=int, default=1, help='Days after today to include.')
        parser.add_argument(
            '--with-teams',
            action='store_true',
            help='Sync teams before syncing fixtures.',
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        from_date = today - timezone.timedelta(days=options['days_back'])
        to_date = today + timezone.timedelta(days=options['days_ahead'])

        sync_options = {
            'from_date': from_date.isoformat(),
            'to_date': to_date.isoformat(),
            'with_teams': options['with_teams'],
        }
        if options.get('competition_id'):
            sync_options['competition_id'] = options['competition_id']
        if options.get('private_league_id'):
            sync_options['private_league_id'] = options['private_league_id']

        self.stdout.write(f'Syncing API fixtures from {from_date} to {to_date}.')
        call_command('sync_api_fixtures', stdout=self.stdout, **sync_options)
