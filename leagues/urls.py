from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('play/<slug:slug>/', views.public_league_landing, name='public_league_landing'),
    path('play/<slug:slug>/rules/', views.league_rules, name='league_rules'),
    path('play/<slug:slug>/join/', views.join_public_league, name='join_public_league'),
    path('signup/', views.signup, name='signup'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('organiser/leagues/', views.organiser_leagues, name='organiser_leagues'),
    path('organiser/leagues/<int:pk>/settings/', views.organiser_league_settings, name='organiser_league_settings'),
    path('organiser/leagues/<int:pk>/sync-fixtures/', views.organiser_sync_fixtures, name='organiser_sync_fixtures'),
    path('organiser/leagues/<int:pk>/teams/', views.organiser_teams, name='organiser_teams'),
    path('organiser/leagues/<int:pk>/teams/new/', views.organiser_team_create, name='organiser_team_create'),
    path('organiser/leagues/<int:league_pk>/teams/<int:team_pk>/edit/', views.organiser_team_edit, name='organiser_team_edit'),
    path('organiser/leagues/<int:league_pk>/teams/<int:team_pk>/delete/', views.organiser_team_delete, name='organiser_team_delete'),
    path('organiser/leagues/<int:pk>/matches/', views.organiser_matches, name='organiser_matches'),
    path('organiser/leagues/<int:pk>/matches/new/', views.organiser_match_create, name='organiser_match_create'),
    path('organiser/leagues/<int:league_pk>/matches/<int:match_pk>/edit/', views.organiser_match_edit, name='organiser_match_edit'),
    path('organiser/leagues/<int:league_pk>/matches/<int:match_pk>/result/', views.organiser_match_result, name='organiser_match_result'),
    path('organiser/leagues/<int:league_pk>/matches/<int:match_pk>/delete/', views.organiser_match_delete, name='organiser_match_delete'),
    path('leagues/create/', views.create_league, name='create_league'),
    path('leagues/join/', views.join_league, name='join_league'),
    path('leagues/<int:pk>/', views.league_detail, name='league_detail'),
    path('leagues/<int:pk>/team/', views.choose_team, name='choose_team'),
    path('leagues/<int:league_pk>/predict/<int:match_pk>/', views.predict, name='predict'),
]
