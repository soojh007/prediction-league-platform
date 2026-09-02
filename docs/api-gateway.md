# Managed Sports Data Feed

If you are self-hosting this platform and do not want to set up your own third-party sports data API subscriptions (such as SportMonks or API-Football), you can request access to our managed fixture and score feed.

---

## 💡 How It Works

1. **Submit an Enquiry**:
   Fill out the request form or email [`hello@predictionleague.site`](mailto:hello@predictionleague.site) with your league details:
   - Competition (e.g. Premier League, Champions League, World Cup)
   - Estimated number of players / private leagues
   - Expected season duration

2. **Receive Your API Token**:
   You will receive a unique API token (e.g. `pl_live_xxxxxxxx`).

3. **Configure Your Instance**:
   Add the token to your `.env` file:
   ```env
   DATA_PROVIDER=managed
   SPORTMONKS_API_TOKEN=pl_live_xxxxxxxx
   ```
4. **Start Syncing**:
   Fixtures and live match results will sync automatically.
