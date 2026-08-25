from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Competition, LeagueMembership, Match, OrganiserEnquiry, Prediction, PrivateLeague, Team


class LoginForm(AuthenticationForm):
    error_messages = {
        'invalid_login': (
            'Please enter the exact username and password. '
            'Username and password are case-sensitive.'
        ),
        'inactive': 'This account is inactive.',
    }


class PlayerLoginForm(LoginForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_staff or user.is_superuser:
            raise forms.ValidationError(
                'Admin accounts must use the organiser login page.',
                code='admin_not_allowed',
            )


class AdminLoginForm(LoginForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not (user.is_staff or user.is_superuser):
            raise forms.ValidationError(
                'Player accounts should use the league login page.',
                code='player_not_allowed',
            )


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class AccountForm(forms.ModelForm):
    first_name = forms.CharField(
        label='Display name',
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Name shown on your profile'}),
    )
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ('first_name', 'email')


class OrganiserEnquiryForm(forms.ModelForm):
    class Meta:
        model = OrganiserEnquiry
        fields = ('name', 'email', 'competition', 'preferred_format', 'estimated_players', 'message')
        labels = {
            'preferred_format': 'Preferred format',
            'estimated_players': 'Estimated players',
        }
        widgets = {
            'competition': forms.TextInput(attrs={'placeholder': 'EPL, SPL, Champions League, office league...'}),
            'estimated_players': forms.NumberInput(attrs={'min': 1, 'placeholder': '20'}),
            'message': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Tell me what you want to run, who it is for, and when you hope to start.',
            }),
        }


class PrivateLeagueForm(forms.ModelForm):
    class Meta:
        model = PrivateLeague
        fields = (
            'name',
            'competition',
            'prediction_mode',
            'ranking_mode',
            'minimum_predictions',
        )
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Saturday Football Pool'}),
            'minimum_predictions': forms.NumberInput(attrs={'min': 1, 'max': 30}),
        }


class LeagueSettingsForm(forms.ModelForm):
    class Meta:
        model = PrivateLeague
        fields = (
            'name',
            'slug',
            'competition',
            'prediction_mode',
            'ranking_mode',
            'minimum_predictions',
            'landing_headline',
            'landing_intro',
            'landing_how_title',
            'landing_how_body',
            'landing_cta',
        )
        widgets = {
            'minimum_predictions': forms.NumberInput(attrs={'min': 1, 'max': 30}),
            'landing_intro': forms.Textarea(attrs={'rows': 4}),
            'landing_how_body': forms.Textarea(attrs={'rows': 4}),
        }


class CompetitionBrandingForm(forms.ModelForm):
    class Meta:
        model = Competition
        fields = ('logo_url', 'api_league_id', 'season')
        labels = {
            'logo_url': 'League logo URL',
            'api_league_id': 'SportMonks season ID',
            'season': 'Display season',
        }
        widgets = {
            'logo_url': forms.URLInput(attrs={'placeholder': 'https://.../league-logo.png'}),
            'api_league_id': forms.NumberInput(attrs={'placeholder': '23690'}),
            'season': forms.NumberInput(attrs={'min': 2000, 'max': 2100}),
        }


class FixtureSyncForm(forms.Form):
    from_date = forms.DateField(
        label='From',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    to_date = forms.DateField(
        label='To',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    sync_teams = forms.BooleanField(
        label='Sync teams and badges first',
        required=False,
        initial=True,
    )

    def clean(self):
        cleaned_data = super().clean()
        from_date = cleaned_data.get('from_date')
        to_date = cleaned_data.get('to_date')
        if from_date and to_date and from_date > to_date:
            raise forms.ValidationError('The sync start date cannot be after the end date.')
        return cleaned_data


class JoinLeagueForm(forms.Form):
    join_code = forms.CharField(max_length=16, widget=forms.TextInput(attrs={'placeholder': 'Enter invite code'}))

    def clean_join_code(self):
        return self.cleaned_data['join_code'].strip().upper()


class SupportedTeamForm(forms.ModelForm):
    class Meta:
        model = LeagueMembership
        fields = ('supported_team',)

    def __init__(self, *args, league=None, **kwargs):
        super().__init__(*args, **kwargs)
        if league is not None:
            self.fields['supported_team'].queryset = league.competition.teams.all()
            self.fields['supported_team'].required = True


class PredictionForm(forms.ModelForm):
    class Meta:
        model = Prediction
        fields = ('predicted_home_score', 'predicted_away_score')
        labels = {
            'predicted_home_score': 'Home score',
            'predicted_away_score': 'Away score',
        }
        widgets = {
            'predicted_home_score': forms.NumberInput(attrs={'min': 0, 'max': 20}),
            'predicted_away_score': forms.NumberInput(attrs={'min': 0, 'max': 20}),
        }


class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = (
            'home_team',
            'away_team',
            'kickoff_time',
            'stage',
            'venue',
            'status',
            'featured',
            'counts_towards_league',
        )
        labels = {
            'counts_towards_league': 'Count towards league table',
        }
        help_texts = {
            'counts_towards_league': 'Turn this off for one-off matches such as Charity Shield or cup fixtures.',
        }
        widgets = {
            'kickoff_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'stage': forms.TextInput(attrs={'placeholder': 'Premier League'}),
            'venue': forms.TextInput(attrs={'placeholder': 'Old Trafford'}),
        }

    def __init__(self, *args, competition=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['kickoff_time'].input_formats = ['%Y-%m-%dT%H:%M']
        if competition is not None:
            teams = competition.teams.all()
            self.fields['home_team'].queryset = teams
            self.fields['away_team'].queryset = teams


class MatchResultForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ('home_score', 'away_score', 'status')
        widgets = {
            'home_score': forms.NumberInput(attrs={'min': 0, 'max': 30}),
            'away_score': forms.NumberInput(attrs={'min': 0, 'max': 30}),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        home_score = cleaned_data.get('home_score')
        away_score = cleaned_data.get('away_score')

        if status == Match.Status.FINISHED and (home_score is None or away_score is None):
            raise forms.ValidationError('Enter both scores before marking the match as finished.')

        return cleaned_data


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ('name', 'short_name', 'logo_url', 'primary_color')
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Manchester United'}),
            'short_name': forms.TextInput(attrs={'placeholder': 'MUN'}),
            'logo_url': forms.URLInput(attrs={'placeholder': 'https://.../team-badge.png'}),
            'primary_color': forms.TextInput(attrs={'type': 'color'}),
        }
