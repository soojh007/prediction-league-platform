from django.db import migrations


def fix_spl_demo_fixtures(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Match = apps.get_model('leagues', 'Match')
    Team = apps.get_model('leagues', 'Team')

    spl = Competition.objects.filter(name='Singapore Premier League').first()
    if spl is None:
        return

    tanjong = Team.objects.filter(competition=spl, name='Tanjong Pagar').first()
    if tanjong is None:
        tanjong = Team.objects.filter(competition=spl, name='Tanjong Pagar United').first()
    if tanjong is None:
        return

    young_lions = Team.objects.filter(competition=spl, name='Young Lions').first()
    geylang = Team.objects.filter(competition=spl, name='Geylang').first()

    if young_lions is not None:
        Match.objects.filter(
            competition=spl,
            home_team=young_lions,
            away_team=young_lions,
        ).update(away_team=tanjong)

    if geylang is not None:
        Match.objects.filter(
            competition=spl,
            home_team=geylang,
            away_team=geylang,
        ).update(home_team=tanjong)


def reverse_spl_demo_fixtures(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('leagues', '0011_add_tanjong_pagar'),
    ]

    operations = [
        migrations.RunPython(fix_spl_demo_fixtures, reverse_spl_demo_fixtures),
    ]
