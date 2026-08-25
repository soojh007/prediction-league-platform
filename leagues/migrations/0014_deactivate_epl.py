from django.db import migrations


def deactivate_epl(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Competition.objects.filter(
        name='Premier League',
        country='England',
        season=2026,
    ).update(active=False)


def reactivate_epl(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Competition.objects.filter(
        name='Premier League',
        country='England',
        season=2026,
    ).update(active=True)


class Migration(migrations.Migration):

    dependencies = [
        ('leagues', '0013_spl_official_team_names'),
    ]

    operations = [
        migrations.RunPython(deactivate_epl, reactivate_epl),
    ]
