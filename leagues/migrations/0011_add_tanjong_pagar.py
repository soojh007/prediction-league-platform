from django.db import migrations


def add_tanjong_pagar(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Team = apps.get_model('leagues', 'Team')

    spl = Competition.objects.filter(name='Singapore Premier League').first()
    if spl is None:
        return

    Team.objects.update_or_create(
        competition=spl,
        name='Tanjong Pagar United',
        defaults={
            'short_name': 'TPU',
            'api_team_id': 10077,
            'logo_url': '/static/leagues/spl/tanjong-pagar-united-2026.png',
            'primary_color': '#1f5aa6',
        },
    )


def remove_tanjong_pagar(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Team = apps.get_model('leagues', 'Team')

    spl = Competition.objects.filter(name='Singapore Premier League').first()
    if spl is None:
        return

    Team.objects.filter(competition=spl, name='Tanjong Pagar United').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('leagues', '0010_spl_team_logos_remove_brunei'),
    ]

    operations = [
        migrations.RunPython(add_tanjong_pagar, remove_tanjong_pagar),
    ]
