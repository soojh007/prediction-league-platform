# API-Football Notes

The platform should use API-Football for:

- competitions
- fixtures
- results
- venues
- standings
- team information
- lineups where available
- odds where available

## Important Data To Store

Store the API IDs so future syncs update existing rows instead of creating duplicates.

```text
competitions.api_league_id
matches.api_fixture_id
```

## Fixture Sync Flow

1. League admin chooses competition and season.
2. System checks if competition exists locally.
3. System calls API-Football fixtures endpoint.
4. System inserts or updates matches by `api_fixture_id`.
5. Match list becomes available for predictions.

## Local Management Commands

Set the API key in the terminal session first:

```bash
export FOOTBALL_API_KEY="your_api_football_key"
```

Sync team names and badges for a private league's competition:

```bash
python manage.py sync_api_teams --private-league-id 1
```

Sync fixtures for a private league's competition. Use a small date window first:

```bash
python manage.py sync_api_fixtures --private-league-id 1 --with-teams --from 2026-08-01 --to 2026-08-31
```

The commands are repeatable. Existing rows are updated by API IDs:

```text
competitions.api_league_id
teams.api_team_id
matches.api_fixture_id
```

## Result Sync Flow

1. Cron job runs every 5-15 minutes during match windows.
2. System checks matches with status not finished.
3. System calls API-Football by fixture ID.
4. If final result exists, update match result.
5. Recalculate points for all predictions on that match.

## Fixture Sync Cron

Fixture sync can be slower, usually hourly or daily:

```bash
curl -fsS "https://example.com/system/sync-fixtures?token=TOKEN" >> /home/app/fixture-sync.log 2>&1
```

## Result Sync Cron

Result sync should run more often:

```bash
curl -fsS "https://example.com/system/sync-results?token=TOKEN" >> /home/app/result-sync.log 2>&1
```
