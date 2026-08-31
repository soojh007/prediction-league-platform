# ⚽ Prediction League Platform

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](#-docker-quick-start)
[![Deploy on Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com)

A modern, developer-friendly football prediction platform built with Django. Designed for private groups, offices, fan clubs, and sports communities to run custom prediction tournaments with automated scoring and dynamic leaderboards.

---

## ✨ Features

- **🏆 Multi-Tenant & Multi-Competition**: Run multiple private leagues simultaneously across competitions like the Premier League, UEFA Champions League, FIFA World Cup, and domestic cups.
- **🎯 Flexible Scoring Engine**: Configurable points for exact scores, correct outcomes (W/D/L), goal differences, and bonus multipliers.
- **📊 Real-Time Leaderboards**: Live standings calculated per private league, with overall platform rankings.
- **🔌 Dual Data Ingestion Modes**:
  - **Managed Data Gateway**: 1-click automated fixture and score sync without third-party rate-limit hassles.
  - **Bring Your Own Key (BYOK)**: Connect personal developer API keys directly from supported sports data providers.
- **🐳 Self-Host Ready**: Fully prepared for local virtual environments, Docker Compose, or one-click deployment on Render.

---

## 🚀 Getting Started

### 1. Local Development (Virtualenv)

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

Access the platform at `http://127.0.0.1:8001`.
- **Demo Admin Login**: `admin` / `admin123`
- **Organiser Portal**: `http://127.0.0.1:8001/organiser/login/`

---

### 2. Docker Quick Start

```bash
# Start the full stack (Web + PostgreSQL)
docker compose up -d
```
Access the platform at `http://localhost:8000`.

---

## ⚙️ Sports Data Ingestion Modes

Configure your preferred data provider in `.env` or production environment variables:

### Option A: Managed Data Gateway (Recommended)
Automated fixture synchronization and live result settlement without managing third-party quotas or cron scrapers:

```bash
SPORTMONKS_API_TOKEN=your_gateway_token_here
```
> 💡 *Need a token? Generate an API key at [predictionleague.site](https://predictionleague.site) for automated fixture and score sync.*

---

### Option B: Bring Your Own Key (BYOK - Free / Self-Managed)
Directly connect your personal API credentials:

```bash
FOOTBALL_API_KEY=your_api_football_key
```

Sync data using management commands:
```bash
# Sync team names and logos:
python manage.py sync_api_teams --private-league-id 1

# Sync fixtures for a date range:
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
| `SPORTMONKS_API_TOKEN` | Managed Data Gateway API token | - | For Managed Gateway |
| `FOOTBALL_API_KEY` | API-Football credentials | - | For Direct BYOK |

---

## 🛠️ Production Deployment (Render)

This repository includes a ready-to-use `render.yaml` blueprint:

1. Push your repository to GitHub.
2. Log into [Render](https://render.com) and create a **New Blueprint Instance**.
3. Select your repository to automatically provision the PostgreSQL database and web service.
4. Set `SPORTMONKS_API_TOKEN` in your Render Environment settings.

---

## 🤝 Contributing

Contributions, bug reports, and feature suggestions are welcome! Please review [CONTRIBUTING.md](CONTRIBUTING.md) and use the provided issue templates.

---

## 📄 License

Distributed under the [MIT License](LICENSE).
