from django.db import migrations


def update_spl_sportmonks_league_id(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Competition.objects.filter(
        name='Singapore Premier League',
        country='Singapore',
    ).update(
        api_league_id=1357,
        season=2026,
        competition_type='API_LEAGUE',
        active=True,
    )


def restore_previous_spl_league_id(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Competition.objects.filter(
        name='Singapore Premier League',
        country='Singapore',
    ).update(api_league_id=505)


class Migration(migrations.Migration):

    dependencies = [
        ('leagues', '0015_configure_spl_sportmonks'),
    ]

    operations = [
        migrations.RunPython(update_spl_sportmonks_league_id, restore_previous_spl_league_id),
    ]
