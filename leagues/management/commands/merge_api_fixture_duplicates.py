from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from leagues.models import Match, Prediction
from leagues.services.sportmonks import resolve_competition


class Command(BaseCommand):
    help = 'Merge duplicate API-created fixtures into existing manually curated fixtures.'

    def add_arguments(self, parser):
        parser.add_argument('--competition-id', type=int, help='Competition row ID to clean.')
        parser.add_argument('--private-league-id', type=int, help='Private league ID whose competition should be cleaned.')
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually merge duplicates. Without this flag, only prints a dry run.',
        )

    def handle(self, *args, **options):
        try:
            competition = resolve_competition(
                competition_id=options.get('competition_id'),
                private_league_id=options.get('private_league_id'),
            )
        except ValueError as error:
            raise CommandError(str(error)) from error

        apply_changes = options['apply']
        pairs = self._find_pairs(competition)

        if not pairs:
            self.stdout.write(self.style.SUCCESS('No duplicate API fixtures found.'))
            return

        self.stdout.write(
            f'Found {len(pairs)} duplicate fixture pair(s) for {competition.name} {competition.season}.'
        )

        for api_match, manual_match in pairs:
            self.stdout.write(
                f'API #{api_match.id} ({api_match.api_fixture_id}) '
                f'{api_match.home_team} vs {api_match.away_team} '
                f'-> manual #{manual_match.id} '
                f'{timezone.localtime(manual_match.kickoff_time):%Y-%m-%d %H:%M}'
            )

        if not apply_changes:
            self.stdout.write(self.style.WARNING('Dry run only. Re-run with --apply to merge these rows.'))
            return

        merged = 0
        moved_predictions = 0
        removed_predictions = 0
        with transaction.atomic():
            for api_match, manual_match in pairs:
                prediction_stats = self._move_predictions(api_match, manual_match)
                moved_predictions += prediction_stats['moved']
                removed_predictions += prediction_stats['removed']
                self._merge_match(api_match, manual_match)
                self._recalculate_predictions(manual_match)
                merged += 1

        self.stdout.write(self.style.SUCCESS(
            f'Merged {merged} duplicate fixture(s). '
            f'Moved {moved_predictions} prediction(s), removed {removed_predictions} duplicate prediction(s).'
        ))

    def _find_pairs(self, competition):
        pairs = []
        api_matches = Match.objects.filter(
            competition=competition,
            api_fixture_id__isnull=False,
        ).select_related('home_team', 'away_team').order_by('kickoff_time', 'id')

        for api_match in api_matches:
            api_local_date = timezone.localtime(api_match.kickoff_time).date()
            candidates = []
            manual_matches = Match.objects.filter(
                competition=competition,
                api_fixture_id__isnull=True,
                home_team=api_match.home_team,
                away_team=api_match.away_team,
            ).select_related('home_team', 'away_team')
            for manual_match in manual_matches:
                if timezone.localtime(manual_match.kickoff_time).date() == api_local_date:
                    candidates.append(manual_match)

            if candidates:
                pairs.append((api_match, self._best_manual_candidate(candidates)))

        return pairs

    def _best_manual_candidate(self, candidates):
        return sorted(
            candidates,
            key=lambda match: (
                not bool(match.venue),
                not bool(match.stage),
                match.id,
            ),
        )[0]

    def _move_predictions(self, api_match, manual_match):
        moved = 0
        removed = 0
        for prediction in list(api_match.predictions.select_related('league', 'user')):
            duplicate = Prediction.objects.filter(
                user=prediction.user,
                league=prediction.league,
                match=manual_match,
            ).first()
            if duplicate:
                prediction.delete()
                removed += 1
            else:
                prediction.match = manual_match
                prediction.save(update_fields=['match', 'points', 'updated_at'])
                moved += 1
        return {'moved': moved, 'removed': removed}

    def _merge_match(self, api_match, manual_match):
        fixture_id = api_match.api_fixture_id
        api_status = api_match.status
        api_home_score = api_match.home_score
        api_away_score = api_match.away_score
        api_stage = api_match.stage

        api_match.delete()

        update_fields = ['api_fixture_id']
        manual_match.api_fixture_id = fixture_id

        if api_status == Match.Status.FINISHED:
            manual_match.status = api_status
            manual_match.home_score = api_home_score
            manual_match.away_score = api_away_score
            update_fields.extend(['status', 'home_score', 'away_score'])

        if not manual_match.stage and api_stage:
            manual_match.stage = api_stage
            update_fields.append('stage')

        manual_match.save(update_fields=update_fields)

    def _recalculate_predictions(self, match):
        for prediction in match.predictions.all():
            prediction.save(update_fields=['points', 'updated_at'])
