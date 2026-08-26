from django.db import migrations


def configure_spl_sportmonks(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Competition.objects.filter(
        name='Singapore Premier League',
        country='Singapore',
    ).update(
        api_league_id=505,
        season=2026,
        competition_type='API_LEAGUE',
        active=True,
    )


def restore_spl_custom(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Competition.objects.filter(
        name='Singapore Premier League',
        country='Singapore',
    ).update(
        competition_type='CUSTOM',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('leagues', '0014_deactivate_epl'),
    ]

    operations = [
        migrations.RunPython(configure_spl_sportmonks, restore_spl_custom),
    ]
