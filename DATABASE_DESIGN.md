# Database Design

This is the proposed starting schema for a multi-league prediction platform.

Use one database. Do not create one database per user or per league.

## Main Tables

```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(254) UNIQUE,
    email_verified TINYINT(1) NOT NULL DEFAULT 0,
    email_reminders_enabled TINYINT(1) NOT NULL DEFAULT 0,
    role VARCHAR(20) NOT NULL DEFAULT 'USER',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE competitions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    api_league_id INT NOT NULL,
    season INT NOT NULL,
    country VARCHAR(100),
    competition_type VARCHAR(30) NOT NULL DEFAULT 'LEAGUE',
    active TINYINT(1) NOT NULL DEFAULT 1,
    UNIQUE KEY uk_competition_api_season (api_league_id, season)
);

CREATE TABLE leagues (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    join_code VARCHAR(30) NOT NULL UNIQUE,
    owner_user_id INT NOT NULL,
    competition_id INT NOT NULL,
    scoring_rule_id INT NULL,
    visibility VARCHAR(20) NOT NULL DEFAULT 'PRIVATE',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES users(id),
    FOREIGN KEY (competition_id) REFERENCES competitions(id)
);

CREATE TABLE league_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    league_id INT NOT NULL,
    user_id INT NOT NULL,
    member_role VARCHAR(20) NOT NULL DEFAULT 'PLAYER',
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_league_user (league_id, user_id),
    FOREIGN KEY (league_id) REFERENCES leagues(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE matches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    competition_id INT NOT NULL,
    api_fixture_id BIGINT UNIQUE,
    home_team VARCHAR(120) NOT NULL,
    away_team VARCHAR(120) NOT NULL,
    kickoff_time DATETIME NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'UPCOMING',
    stage VARCHAR(60),
    venue VARCHAR(120),
    city VARCHAR(120),
    home_score INT NULL,
    away_score INT NULL,
    winning_side VARCHAR(10) NULL,
    decided_by VARCHAR(20) NULL,
    FOREIGN KEY (competition_id) REFERENCES competitions(id),
    INDEX idx_matches_competition_kickoff (competition_id, kickoff_time)
);

CREATE TABLE predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    match_id INT NOT NULL,
    predicted_home_score INT NOT NULL,
    predicted_away_score INT NOT NULL,
    predicted_winner_side VARCHAR(10) NULL,
    predicted_decided_by VARCHAR(20) NULL,
    points INT NOT NULL DEFAULT 0,
    knockout_bonus_points INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_match (user_id, match_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (match_id) REFERENCES matches(id)
);
```

## Why Predictions Are Not League-Specific At First

The first version should let one prediction count across every private league the user belongs to.

Example:

- Aung joins Office League and Friends League.
- Both leagues use the same World Cup competition.
- Aung predicts Spain 2-1 France once.
- That prediction counts in both leagues.

This avoids duplicate prediction work and keeps the product simple.

## Later Tables

Add these after the MVP is stable:

```sql
CREATE TABLE scoring_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    exact_score_points INT NOT NULL DEFAULT 7,
    correct_result_points INT NOT NULL DEFAULT 3,
    goal_difference_bonus INT NOT NULL DEFAULT 1,
    home_goals_bonus INT NOT NULL DEFAULT 1,
    away_goals_bonus INT NOT NULL DEFAULT 1,
    knockout_winner_points INT NOT NULL DEFAULT 3,
    knockout_method_points INT NOT NULL DEFAULT 1
);

CREATE TABLE payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    league_id INT NOT NULL,
    user_id INT NOT NULL,
    provider VARCHAR(30) NOT NULL,
    provider_reference VARCHAR(120),
    amount_cents INT NOT NULL,
    currency CHAR(3) NOT NULL,
    status VARCHAR(30) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (league_id) REFERENCES leagues(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE announcements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    league_id INT NULL,
    title VARCHAR(160) NOT NULL,
    message TEXT NOT NULL,
    active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (league_id) REFERENCES leagues(id)
);
```

