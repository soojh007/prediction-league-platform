from django.db import migrations


def update_tanjong_pagar_branding(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Team = apps.get_model('leagues', 'Team')
    spl = Competition.objects.filter(
        name='Singapore Premier League',
        country='Singapore',
    ).first()
    if not spl:
        return

    Team.objects.filter(
        competition=spl,
        name='Tanjong Pagar',
    ).update(
        name='Tanjong Pagar United',
        short_name='TPU',
        logo_url='/static/leagues/spl/tanjong-pagar-united.png',
    )
    Team.objects.filter(
        competition=spl,
        name='Tanjong Pagar United',
    ).update(
        short_name='TPU',
        logo_url='/static/leagues/spl/tanjong-pagar-united.png',
    )


def reverse_tanjong_pagar_branding(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Team = apps.get_model('leagues', 'Team')
    spl = Competition.objects.filter(
        name='Singapore Premier League',
        country='Singapore',
    ).first()
    if not spl:
        return

    Team.objects.filter(
        competition=spl,
        name='Tanjong Pagar United',
    ).update(
        name='Tanjong Pagar',
        short_name='TPU',
        logo_url='/static/leagues/spl/tanjong-pagar-united-2026.png',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('leagues', '0017_competition_api_season_id'),
    ]

    operations = [
        migrations.RunPython(update_tanjong_pagar_branding, reverse_tanjong_pagar_branding),
    ]
