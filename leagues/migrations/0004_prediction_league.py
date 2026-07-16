# Generated manually on 2026-07-13

from django.db import migrations, models
import django.db.models.deletion


def attach_existing_predictions_to_leagues(apps, schema_editor):
    Prediction = apps.get_model('leagues', 'Prediction')
    LeagueMembership = apps.get_model('leagues', 'LeagueMembership')
    PrivateLeague = apps.get_model('leagues', 'PrivateLeague')

    for prediction in Prediction.objects.select_related('match', 'user'):
        league = (
            LeagueMembership.objects
            .filter(
                user_id=prediction.user_id,
                league__competition_id=prediction.match.competition_id,
            )
            .order_by('league_id')
            .values_list('league_id', flat=True)
            .first()
        )

        if league is None:
            league = (
                PrivateLeague.objects
                .filter(competition_id=prediction.match.competition_id)
                .order_by('id')
                .values_list('id', flat=True)
                .first()
            )

        prediction.league_id = league
        prediction.save(update_fields=['league'])


class Migration(migrations.Migration):

    dependencies = [
        ('leagues', '0003_privateleague_landing_cta_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='prediction',
            name='league',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='predictions',
                to='leagues.privateleague',
            ),
        ),
        migrations.RunPython(attach_existing_predictions_to_leagues, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='prediction',
            unique_together={('user', 'league', 'match')},
        ),
        migrations.AlterField(
            model_name='prediction',
            name='league',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='predictions',
                to='leagues.privateleague',
            ),
        ),
    ]
