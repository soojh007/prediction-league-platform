from django.db import migrations


def update_spl_teams(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Match = apps.get_model('leagues', 'Match')
    Team = apps.get_model('leagues', 'Team')

    spl = Competition.objects.filter(name='Singapore Premier League').first()
    if spl is None:
        return

    logo_updates = {
        'Balestier': {
            'logo_url': '/static/leagues/spl/balestier.png',
            'primary_color': '#d9272e',
        },
        'Geylang': {
            'logo_url': '/static/leagues/spl/geylangunited.png',
            'primary_color': '#138a3d',
        },
        'Hougang': {
            'logo_url': '/static/leagues/spl/hougang.png',
            'primary_color': '#f47b20',
        },
        'Lion City': {
            'logo_url': '/static/leagues/spl/lioncitysailors.png',
            'primary_color': '#214f9f',
        },
        'Tampines': {
            'logo_url': '/static/leagues/spl/tampines.png',
            'primary_color': '#ffd200',
        },
        'Young Lions': {
            'logo_url': '/static/leagues/spl/younglions.png',
            'primary_color': '#e31b23',
        },
    }

    for team_name, values in logo_updates.items():
        Team.objects.filter(competition=spl, name=team_name).update(**values)

    brunei = Team.objects.filter(competition=spl, name='Brunei DPMM').first()
    if brunei is None:
        return

    young_lions = Team.objects.filter(competition=spl, name='Young Lions').first()
    geylang = Team.objects.filter(competition=spl, name='Geylang').first()
    if young_lions is not None:
        Match.objects.filter(competition=spl, away_team=brunei).update(away_team=young_lions)
    if geylang is not None:
        Match.objects.filter(competition=spl, home_team=brunei).update(home_team=geylang)
    brunei.delete()


def reverse_spl_teams(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Team = apps.get_model('leagues', 'Team')

    spl = Competition.objects.filter(name='Singapore Premier League').first()
    if spl is None:
        return

    Team.objects.get_or_create(
        competition=spl,
        name='Brunei DPMM',
        defaults={
            'short_name': 'DPM',
            'primary_color': '#222222',
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('leagues', '0009_spl_branding'),
    ]

    operations = [
        migrations.RunPython(update_spl_teams, reverse_spl_teams),
    ]
