from django.db import migrations


def apply_spl_branding(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Team = apps.get_model('leagues', 'Team')

    spl = Competition.objects.filter(name='Singapore Premier League').first()
    if spl is None:
        return

    spl.api_league_id = spl.api_league_id or 368
    if not spl.logo_url:
        spl.logo_url = 'https://media.api-sports.io/football/leagues/368.png'
    spl.save(update_fields=['api_league_id', 'logo_url'])

    local_branding = {
        'Albirex': {
            'name': 'FC Jurong',
            'short_name': 'FCJ',
            'api_team_id': 4200,
            'logo_url': '/static/leagues/spl/fc-jurong-2026.png',
            'primary_color': '#ec2b35',
        },
        'FC Jurong': {
            'name': 'FC Jurong',
            'short_name': 'FCJ',
            'api_team_id': 4200,
            'logo_url': '/static/leagues/spl/fc-jurong-2026.png',
            'primary_color': '#ec2b35',
        },
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
        'Tanjong Pagar United': {
            'name': 'Tanjong Pagar United',
            'short_name': 'TPU',
            'api_team_id': 10077,
            'logo_url': '/static/leagues/spl/tanjong-pagar-united-2026.png',
            'primary_color': '#1f5aa6',
        },
        'Young Lions': {
            'logo_url': '/static/leagues/spl/younglions.png',
            'primary_color': '#e31b23',
        },
    }

    for lookup_name, values in local_branding.items():
        team = Team.objects.filter(competition=spl, name=lookup_name).first()
        if team is None:
            continue
        for field, value in values.items():
            setattr(team, field, value)
        team.save(update_fields=list(values.keys()))


def remove_spl_branding(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Team = apps.get_model('leagues', 'Team')

    spl = Competition.objects.filter(name='Singapore Premier League').first()
    if spl is None:
        return

    Team.objects.filter(competition=spl, name='FC Jurong').update(
        name='Albirex',
        short_name='ALB',
        api_team_id=None,
        logo_url='',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('leagues', '0008_match_counts_towards_league'),
    ]

    operations = [
        migrations.RunPython(apply_spl_branding, remove_spl_branding),
    ]
