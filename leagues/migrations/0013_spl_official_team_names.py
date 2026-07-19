from django.db import migrations


def use_official_spl_names(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Team = apps.get_model('leagues', 'Team')

    spl = Competition.objects.filter(name='Singapore Premier League').first()
    if spl is None:
        return

    renames = {
        'Lion City': 'Lion City Sailors',
        'Tampines': 'Tampines Rovers',
        'Balestier': 'Balestier Khalsa',
        'Geylang': 'Geylang International',
        'Hougang': 'Hougang United',
        'Tanjong Pagar United': 'Tanjong Pagar',
    }

    for old_name, new_name in renames.items():
        Team.objects.filter(competition=spl, name=old_name).update(name=new_name)


def reverse_official_spl_names(apps, schema_editor):
    Competition = apps.get_model('leagues', 'Competition')
    Team = apps.get_model('leagues', 'Team')

    spl = Competition.objects.filter(name='Singapore Premier League').first()
    if spl is None:
        return

    renames = {
        'Lion City Sailors': 'Lion City',
        'Tampines Rovers': 'Tampines',
        'Balestier Khalsa': 'Balestier',
        'Geylang International': 'Geylang',
        'Hougang United': 'Hougang',
        'Tanjong Pagar': 'Tanjong Pagar United',
    }

    for old_name, new_name in renames.items():
        Team.objects.filter(competition=spl, name=old_name).update(name=new_name)


class Migration(migrations.Migration):

    dependencies = [
        ('leagues', '0012_fix_spl_demo_fixtures'),
    ]

    operations = [
        migrations.RunPython(use_official_spl_names, reverse_official_spl_names),
    ]
