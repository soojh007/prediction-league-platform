from django.db import migrations, models


def set_spl_sportmonks_season(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Competition.objects.filter(
        name='Singapore Premier League',
        country='Singapore',
    ).update(
        api_league_id=1357,
        api_season_id=28091,
        season=2026,
        competition_type='API_LEAGUE',
        active=True,
    )


def reverse_spl_sportmonks_season(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Competition.objects.filter(
        name='Singapore Premier League',
        country='Singapore',
    ).update(api_season_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('leagues', '0016_update_spl_sportmonks_league_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='competition',
            name='api_season_id',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RunPython(set_spl_sportmonks_season, reverse_spl_sportmonks_season),
    ]
