# Managed Sports Data Gateway

The **Managed Sports Data Gateway** is a high-performance caching and normalization service providing real-time fixtures, team metadata, and automated match score settlement for self-hosted instances of Prediction League Platform.

---

## 💡 Why Use the Managed Gateway?

1. **Avoid Upstream Rate Limits**:
   Direct third-party sports data feeds often restrict free tiers to strict caps (e.g. 10 requests/minute or 100/day). The managed gateway continuously caches and distributes live scores so your private leagues never miss a live result during busy matchdays.
2. **Standardized Data Schema**:
   Eliminate the hassle of data differences across multiple sports providers. The gateway normalizes tournament schedules, team logos, and match states.
3. **Automated Settlement**:
   Match outcomes and leaderboards automatically settle within minutes of full-time whistles without requiring custom cron scripts or server maintenance.

---

## 🔑 Getting Started with Your Token

1. Create an account and generate an API token at [predictionleague.site](https://predictionleague.site).
2. Add your token to your local `.env` or production environment variables:
   ```bash
   SPORTMONKS_API_TOKEN=your_managed_gateway_token_here
   ```
3. Restart your application. Fixture and score synchronization will now run seamlessly through the gateway.

---

## 🛠️ Data Synchronization Commands

When running with a valid token, sync tournaments and fixtures directly via Django management commands:

```bash
# Sync team names and badges for a private league's competition:
python manage.py sync_api_teams --private-league-id 1

# Sync fixtures for a date window:
python manage.py sync_api_fixtures --private-league-id 1 --with-teams --from 2026-08-01 --to 2026-08-31
```
