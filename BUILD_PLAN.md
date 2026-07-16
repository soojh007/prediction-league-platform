# Build Plan

## Phase 1: Product Foundation

Goal: Turn the current World Cup idea into a general private prediction league product.

Design principle:

- Build mobile-first from the start. Most users will predict from phones, so every core flow must work cleanly on a narrow screen before desktop polish.

Tasks:

1. Decide stack.
2. Create new project.
3. Add user registration and login.
4. Add competitions table.
5. Add private league creation.
6. Add join-by-code.
7. Add fixture sync by competition.
8. Add predictions.
9. Add league leaderboard.

Recommended stack choices:

- Fastest from current app: Java Servlet/JSP/Tomcat/MySQL
- Better long-term SaaS: Node.js/Express or Next.js with MySQL/PostgreSQL
- Simplest admin-heavy backend: Python Django

If the goal is to launch quickly from the existing code, start with Java.
If the goal is a polished paid SaaS, consider Node.js/Next.js or Django.

## Phase 2: Admin Tools

Tasks:

1. League admin dashboard
2. Manage members
3. Remove users from league
4. Edit league name and settings
5. Add league announcements
6. View all predictions in league
7. Export leaderboard to CSV

## Phase 3: Automation

Tasks:

1. Sync fixtures from API-Football
2. Sync results automatically
3. Recalculate points after results update
4. Email reminders before unpredicted matches
5. Audit log for predictions and result changes

## Phase 4: Payments

Tasks:

1. Add pricing tiers
2. Add Stripe Checkout or payment provider
3. Lock premium features behind paid league plan
4. Add invoice/payment status view for league owner

## Phase 5: Customisation

Tasks:

1. League logo
2. League banner
3. Custom scoring rules
4. Public/private league setting
5. League landing page
6. Optional subdomain support

## Phase 6: Marketing Site

Pages:

1. Home
2. Pricing
3. Demo league
4. Create league
5. FAQ
6. Contact

Main positioning:

> Create a private football prediction league for your friends, office, school, or fan community. No spreadsheets. Automatic fixtures, scoring, reminders, and leaderboards.
