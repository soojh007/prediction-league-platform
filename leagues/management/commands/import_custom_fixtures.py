import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from leagues.models import Competition, Match, PrivateLeague, Team


TRUE_VALUES = {'1', 'true', 'yes', 'y', 'on'}


class Command(BaseCommand):
    help = 'Import custom fixtures from a CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', help='Path to a CSV file with fixture rows.')
        parser.add_argument('--competition-id', type=int, help='Competition row ID to import into.')
        parser.add_argument('--private-league-id', type=int, help='Private league ID whose competition should be used.')
        parser.add_argument('--private-league-slug', help='Private league slug whose competition should be used.')
        parser.add_argument(
            '--create-teams',
            action='store_true',
            help='Create missing teams in the competition instead of failing.',
        )

    def handle(self, *args, **options):
        competition = self.resolve_competition(options)
        csv_path = Path(options['csv_path'])
        if not csv_path.exists():
            raise CommandError(f'CSV file not found: {csv_path}')

        checked = created = updated = skipped = 0
        with csv_path.open(newline='') as csv_file:
            reader = csv.DictReader(csv_file)
            required = {'kickoff_time', 'home_team', 'away_team'}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise CommandError(f'Missing required CSV columns: {", ".join(sorted(missing))}')

            for row_number, row in enumerate(reader, start=2):
                checked += 1
                home_name = clean(row.get('home_team'))
                away_name = clean(row.get('away_team'))
                kickoff = parse_kickoff(row.get('kickoff_time'), row_number)

                if not home_name or not away_name:
                    skipped += 1
                    self.stderr.write(f'Row {row_number}: skipped because a team name is blank.')
                    continue
                if home_name == away_name:
                    skipped += 1
                    self.stderr.write(f'Row {row_number}: skipped because home and away teams are the same.')
                    continue

                home_team = self.get_team(competition, home_name, options['create_teams'], row_number)
                away_team = self.get_team(competition, away_name, options['create_teams'], row_number)
                defaults = {
                    'stage': clean(row.get('stage')) or 'League',
                    'venue': clean(row.get('venue')),
                    'featured': parse_bool(row.get('featured')),
                    'counts_towards_league': parse_bool(row.get('counts_towards_league'), default=True),
                }

                _, was_created = Match.objects.update_or_create(
                    competition=competition,
                    home_team=home_team,
                    away_team=away_team,
                    kickoff_time=kickoff,
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Fixture import complete for {competition.name} {competition.season}. '
            f'Checked: {checked}. Created: {created}. Updated: {updated}. Skipped: {skipped}.'
        ))

    def resolve_competition(self, options):
        identifiers = [
            bool(options.get('competition_id')),
            bool(options.get('private_league_id')),
            bool(options.get('private_league_slug')),
        ]
        if sum(identifiers) != 1:
            raise CommandError('Provide exactly one of --competition-id, --private-league-id, or --private-league-slug.')

        if options.get('competition_id'):
            return Competition.objects.get(pk=options['competition_id'])
        if options.get('private_league_id'):
            return PrivateLeague.objects.select_related('competition').get(pk=options['private_league_id']).competition
        return PrivateLeague.objects.select_related('competition').get(slug=options['private_league_slug']).competition

    def get_team(self, competition, name, create_missing, row_number):
        if create_missing:
            team, _ = Team.objects.get_or_create(competition=competition, name=name)
            return team

        try:
            return Team.objects.get(competition=competition, name=name)
        except Team.DoesNotExist as error:
            raise CommandError(f'Row {row_number}: team not found in {competition.name}: {name}') from error


def clean(value):
    return (value or '').strip()


def parse_bool(value, default=False):
    value = clean(value).lower()
    if value == '':
        return default
    return value in TRUE_VALUES


def parse_kickoff(value, row_number):
    kickoff = parse_datetime(clean(value))
    if kickoff is None:
        raise CommandError(f'Row {row_number}: invalid kickoff_time: {value}')
    if timezone.is_naive(kickoff):
        kickoff = timezone.make_aware(kickoff, timezone.get_current_timezone())
    return kickoff
