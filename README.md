# ⚽ Prediction League Platform

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](#-docker-quick-start)
[![Deploy on Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com)

A modern, customizable football prediction platform built with Django. Designed for private groups, offices, fan clubs, and sports communities to run custom prediction tournaments with automated scoring and dynamic leaderboards.

---

## 🌟 Two Ways to Use

### 1. 🛠️ Self-Hosted (Free & Open-Source)
Fork this repository to deploy and manage the application on your own infrastructure (Docker, VPS, or Render). Bring your own sports data API key or use the built-in demo datasets.

### 2. ⚡ Managed Hosting Service (Turnkey)
Don't want to deal with servers, databases, or sports API subscriptions?
- We host your private league on [predictionleague.site](https://predictionleague.site).
- You get a dedicated **Organiser Admin Account** (`/organiser/login/`) to manage match fixtures, customize scoring rules, view predictions, and invite players.
- Live fixtures and match scores update automatically.
- **[Request a Managed League](docs/managed-hosting.md)** or contact [`hello@predictionleague.site`](mailto:hello@predictionleague.site).

---

## ✨ Platform Features

- **🏆 Multi-League & Multi-Competition**: Run private leagues across the Premier League, UEFA Champions League, FIFA World Cup, and domestic cups.
- **🎯 Flexible Scoring Engine**: Set custom points for exact scores, correct outcomes (W/D/L), and goal differences.
- **📊 Real-Time Leaderboards**: Live standings calculated per private league, with overall platform rankings.
- **👨‍💼 Organiser Management Portal**: League admins can invite players via private codes/links, configure matchdays, and post announcements.
- **🐳 Self-Host Ready**: Run locally with a Python virtualenv, via Docker Compose, or deploy to Render in 1 click.

---

## 🚀 Quick Start (Self-Hosted)

### Local Development with Virtualenv

```bash
# 1. Clone the repository
git clone https://github.com/soojh007/prediction-league-platform.git
cd prediction-league-platform

# 2. Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment configuration
cp .env.example .env

# 5. Apply migrations and seed demo data
python manage.py migrate
python manage.py seed_demo

# 6. Start development server
python manage.py runserver 127.0.0.1:8001
```

Access the platform at `http://127.0.0.1:8001`:
- **Demo Player Login**: `player1` / `admin123`
- **Organiser Admin Portal**: `http://127.0.0.1:8001/organiser/login/` (`admin` / `admin123`)

---

### Docker Quick Start

```bash
docker compose up -d
```
Access the platform at `http://localhost:8000`.

---

## ⚙️ Sports Data Feed (Self-Hosted)

If you are self-hosting and want live data sync, add your API key in `.env`:

```bash
FOOTBALL_API_KEY=your_api_football_key
# or
SPORTMONKS_API_TOKEN=your_sportmonks_token
```

Run sync commands:
```bash
# Sync team names and badges:
python manage.py sync_api_teams --private-league-id 1

# Sync fixtures:
python manage.py sync_api_fixtures --private-league-id 1 --with-teams --from 2026-08-01 --to 2026-08-31
```

---

## 📋 Environment Variables Reference

| Variable | Description | Default | Required |
| :--- | :--- | :--- | :--- |
| `DEBUG` | Enable/disable debug mode | `True` | No |
| `SECRET_KEY` | Django cryptographic secret | - | Yes (in production) |
| `ALLOWED_HOSTS` | Comma-separated list of valid hostnames | `127.0.0.1,localhost` | Yes |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated list of trusted origins | - | If deployed over HTTPS |
| `DATABASE_URL` | PostgreSQL connection URL | SQLite (`db.sqlite3`) | No |
| `SPORTMONKS_API_TOKEN` | SportMonks API token | - | For live SportMonks sync |
| `FOOTBALL_API_KEY` | API-Football API key | - | For live API-Football sync |

---

## 🛠️ Production Deployment (Render)

This repository includes a ready-to-use `render.yaml` blueprint:

1. Push your repository to GitHub.
2. In [Render](https://render.com), create a **New Blueprint Instance**.
3. Link your repository to automatically provision the web service and PostgreSQL database.

---

## 🤝 Contributing

Contributions, bug reports, and pull requests are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## 📄 License

Distributed under the [MIT License](LICENSE).
