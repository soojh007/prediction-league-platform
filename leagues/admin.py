from django.contrib import admin
from .models import Competition, LeagueMembership, Match, OrganiserEnquiry, Prediction, PrivateLeague, Team


class TeamInline(admin.TabularInline):
    model = Team
    extra = 0


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'season', 'api_league_id', 'competition_type', 'country', 'active')
    list_filter = ('competition_type', 'active')
    search_fields = ('name', 'country')
    inlines = [TeamInline]


@admin.register(PrivateLeague)
class PrivateLeagueAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'competition', 'prediction_mode', 'ranking_mode', 'join_code', 'owner')
    list_filter = ('prediction_mode', 'ranking_mode', 'competition')
    search_fields = ('name', 'slug', 'join_code', 'owner__username')
    fieldsets = (
        ('League setup', {
            'fields': (
                'name',
                'slug',
                'owner',
                'competition',
                'join_code',
                'prediction_mode',
                'ranking_mode',
                'minimum_predictions',
            )
        }),
        ('Landing page', {
            'fields': (
                'landing_headline',
                'landing_intro',
                'landing_how_title',
                'landing_how_body',
                'landing_cta',
            )
        }),
    )


@admin.register(LeagueMembership)
class LeagueMembershipAdmin(admin.ModelAdmin):
    list_display = ('league', 'user', 'supported_team', 'role', 'joined_at')
    list_filter = ('role', 'league')
    search_fields = ('user__username', 'league__name', 'supported_team__name')


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('home_team', 'away_team', 'competition', 'kickoff_time', 'status', 'featured', 'api_fixture_id')
    list_filter = ('competition', 'status', 'featured')
    search_fields = ('home_team__name', 'away_team__name', 'venue')


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ('user', 'league', 'match', 'predicted_home_score', 'predicted_away_score', 'points')
    list_filter = ('league', 'match__competition')
    search_fields = ('user__username', 'league__name', 'match__home_team__name', 'match__away_team__name')


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'competition', 'api_team_id')
    list_filter = ('competition',)
    search_fields = ('name', 'short_name')


@admin.register(OrganiserEnquiry)
class OrganiserEnquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'competition', 'preferred_format', 'estimated_players', 'handled', 'created_at')
    list_filter = ('preferred_format', 'handled', 'created_at')
    search_fields = ('name', 'email', 'competition', 'message')
    readonly_fields = ('created_at',)
