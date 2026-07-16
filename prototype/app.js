const state = {
    leagueName: "Saturday Football Pool",
    competition: "epl",
    mode: "supporter",
    ranking: "total",
    minimumPredictions: 5,
    supportedClub: "Liverpool"
};

const competitions = {
    epl: {
        label: "Premier League",
        teamLabel: "Premier League clubs",
        clubs: [
            ["Arsenal", "ARS", "#d9293f"],
            ["Aston Villa", "AVL", "#6f1d46"],
            ["Chelsea", "CHE", "#1b55b8"],
            ["Liverpool", "LIV", "#c8102e"],
            ["Manchester City", "MCI", "#6cabdd"],
            ["Manchester United", "MUN", "#da291c"],
            ["Newcastle", "NEW", "#1d1d1d"],
            ["Tottenham", "TOT", "#10223f"]
        ],
        fixtures: [
            ["Liverpool", "Arsenal", "Sat 17 Aug", "7:30 pm", true],
            ["Chelsea", "Manchester City", "Sun 18 Aug", "11:30 pm", true],
            ["Manchester United", "Liverpool", "Sat 24 Aug", "10:00 pm", true],
            ["Tottenham", "Newcastle", "Sun 25 Aug", "9:00 pm", false],
            ["Arsenal", "Chelsea", "Sat 31 Aug", "7:30 pm", true],
            ["Aston Villa", "Manchester United", "Sun 01 Sep", "11:30 pm", false],
            ["Manchester City", "Liverpool", "Sat 14 Sep", "10:00 pm", true],
            ["Newcastle", "Arsenal", "Sun 15 Sep", "9:00 pm", false]
        ]
    },
    custom: {
        label: "Custom 8-club league",
        teamLabel: "Custom league clubs",
        clubs: [
            ["Tampines", "TAM", "#f38b00"],
            ["Lion City", "LCS", "#2148b5"],
            ["Albirex", "ALB", "#f26522"],
            ["Hougang", "HOU", "#d62828"],
            ["Geylang", "GEY", "#188f5c"],
            ["Balestier", "BAL", "#c62838"],
            ["Young Lions", "YLI", "#3f7fc1"],
            ["Brunei DPMM", "DPM", "#222222"]
        ],
        fixtures: [
            ["Tampines", "Lion City", "Fri 21 Aug", "8:15 pm", true],
            ["Albirex", "Hougang", "Sat 22 Aug", "6:00 pm", false],
            ["Geylang", "Balestier", "Sat 22 Aug", "8:15 pm", false],
            ["Young Lions", "Brunei DPMM", "Sun 23 Aug", "6:00 pm", true],
            ["Lion City", "Albirex", "Fri 28 Aug", "8:15 pm", true],
            ["Hougang", "Tampines", "Sat 29 Aug", "6:00 pm", true],
            ["Balestier", "Young Lions", "Sat 29 Aug", "8:15 pm", false],
            ["Brunei DPMM", "Geylang", "Sun 30 Aug", "6:00 pm", false]
        ]
    }
};

const modeCopy = {
    all: {
        title: "All matches",
        text: "Every player predicts every match in the selected competition. This is best for smaller competitions or highly engaged groups.",
        matches: "All fixtures",
        ranking: "Total points",
        bestFor: "Serious leagues"
    },
    supporter: {
        title: "Supported club only",
        text: "Each player chooses one club and only predicts matches involving that club. This is ideal for EPL fan groups and smaller club communities.",
        matches: "38 for EPL",
        ranking: "Total points",
        bestFor: "Fan groups"
    },
    featured: {
        title: "Featured matches only",
        text: "The admin selects big matches or weekly fixtures. Everyone predicts the same smaller set, making it fair and casual-friendly.",
        matches: "Admin selected",
        ranking: "Total points",
        bestFor: "Office pools"
    }
};

const sampleUsers = [
    { name: "Aung", club: "Liverpool", predictions: 18, exact: 5, points: 94 },
    { name: "Roy", club: "Arsenal", predictions: 15, exact: 4, points: 81 },
    { name: "Blue", club: "Chelsea", predictions: 12, exact: 4, points: 79 },
    { name: "Jun Kai", club: "Manchester City", predictions: 21, exact: 3, points: 88 },
    { name: "soojh007", club: "Liverpool", predictions: 9, exact: 2, points: 54 },
    { name: "Eston", club: "Newcastle", predictions: 6, exact: 1, points: 37 }
];

const elements = {};

document.addEventListener("DOMContentLoaded", () => {
    bindElements();
    loadState();
    bindEvents();
    render();
});

function bindElements() {
    [
        "leagueForm", "leagueName", "competition", "mode", "ranking",
        "minimumPredictions", "previewTitle", "previewText", "matchesPerPlayer",
        "fairRanking", "bestFor", "clubGrid", "teamListTitle", "teamCount",
        "supportedClub", "supporterHelp", "fixtureList", "fixtureTitle",
        "fixtureCount", "playerLeagueTitle", "playerModePill", "nextDeadline",
        "deadlineText", "leaderboardRows", "mainRankingTitle", "clubLeaderboard",
        "resetPrototype"
    ].forEach((id) => {
        elements[id] = document.getElementById(id);
    });
}

function bindEvents() {
    document.querySelectorAll(".nav-button").forEach((button) => {
        button.addEventListener("click", () => {
            document.querySelectorAll(".nav-button").forEach((item) => item.classList.remove("active"));
            document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
            button.classList.add("active");
            document.getElementById(button.dataset.view).classList.add("active");
        });
    });

    ["leagueName", "competition", "mode", "ranking", "minimumPredictions"].forEach((id) => {
        elements[id].addEventListener("input", updateStateFromForm);
    });

    elements.supportedClub.addEventListener("change", () => {
        state.supportedClub = elements.supportedClub.value;
        saveState();
        renderFixtures();
        renderLeaderboards();
    });

    elements.leagueForm.addEventListener("submit", (event) => {
        event.preventDefault();
        updateStateFromForm();
        flashButton(event.submitter, "Saved");
    });

    elements.resetPrototype.addEventListener("click", () => {
        localStorage.removeItem("predictionLeaguePrototype");
        Object.assign(state, {
            leagueName: "Saturday Football Pool",
            competition: "epl",
            mode: "supporter",
            ranking: "total",
            minimumPredictions: 5,
            supportedClub: "Liverpool"
        });
        render();
    });
}

function loadState() {
    const saved = localStorage.getItem("predictionLeaguePrototype");
    if (!saved) {
        return;
    }
    try {
        Object.assign(state, JSON.parse(saved));
    } catch (error) {
        localStorage.removeItem("predictionLeaguePrototype");
    }
}

function saveState() {
    localStorage.setItem("predictionLeaguePrototype", JSON.stringify(state));
}

function updateStateFromForm() {
    state.leagueName = elements.leagueName.value.trim() || "Untitled League";
    state.competition = elements.competition.value;
    state.mode = elements.mode.value;
    state.ranking = elements.ranking.value;
    state.minimumPredictions = Number(elements.minimumPredictions.value) || 1;

    const clubs = competitions[state.competition].clubs.map((club) => club[0]);
    if (!clubs.includes(state.supportedClub)) {
        state.supportedClub = clubs[0];
    }

    saveState();
    render();
}

function render() {
    elements.leagueName.value = state.leagueName;
    elements.competition.value = state.competition;
    elements.mode.value = state.mode;
    elements.ranking.value = state.ranking;
    elements.minimumPredictions.value = state.minimumPredictions;

    renderModePreview();
    renderClubs();
    renderPlayerControls();
    renderFixtures();
    renderLeaderboards();
}

function renderModePreview() {
    const copy = modeCopy[state.mode];
    elements.previewTitle.textContent = copy.title;
    elements.previewText.textContent = copy.text;
    elements.matchesPerPlayer.textContent = state.mode === "supporter" && state.competition === "custom" ? "14-21" : copy.matches;
    elements.fairRanking.textContent = state.ranking === "average" ? "Average points" : copy.ranking;
    elements.bestFor.textContent = copy.bestFor;
}

function renderClubs() {
    const competition = competitions[state.competition];
    elements.teamListTitle.textContent = competition.teamLabel;
    elements.teamCount.textContent = `${competition.clubs.length} clubs`;
    elements.clubGrid.innerHTML = competition.clubs.map(([name, code, color]) => `
        <div class="club-card">
            <span class="crest" style="--club-color: ${color}">${code.slice(0, 1)}</span>
            <div>
                <strong>${name}</strong>
                <div class="club-code">${code}</div>
            </div>
        </div>
    `).join("");
}

function renderPlayerControls() {
    const competition = competitions[state.competition];
    elements.playerLeagueTitle.textContent = state.leagueName;
    elements.playerModePill.textContent = modeCopy[state.mode].title;
    elements.supportedClub.innerHTML = competition.clubs.map(([name]) => `
        <option value="${name}" ${name === state.supportedClub ? "selected" : ""}>${name}</option>
    `).join("");
    elements.supportedClub.disabled = state.mode !== "supporter";

    if (state.mode === "supporter") {
        elements.supporterHelp.textContent = `You only predict ${state.supportedClub} matches. The club is usually locked after your first prediction.`;
    } else if (state.mode === "featured") {
        elements.supporterHelp.textContent = "Your club choice is optional. Everyone predicts the same featured matches chosen by the league admin.";
    } else {
        elements.supporterHelp.textContent = "Everyone predicts every match in this competition.";
    }
}

function getVisibleFixtures() {
    const fixtures = competitions[state.competition].fixtures;
    if (state.mode === "all") {
        return fixtures;
    }
    if (state.mode === "featured") {
        return fixtures.filter((fixture) => fixture[4]);
    }
    return fixtures.filter((fixture) => fixture[0] === state.supportedClub || fixture[1] === state.supportedClub);
}

function renderFixtures() {
    const fixtures = getVisibleFixtures();
    elements.fixtureTitle.textContent = state.mode === "supporter" ? `${state.supportedClub} fixtures` : "Upcoming matches";
    elements.fixtureCount.textContent = `${fixtures.length} matches`;

    if (fixtures.length) {
        elements.nextDeadline.textContent = `${fixtures[0][2]}, ${fixtures[0][3]}`;
        elements.deadlineText.textContent = `${fixtures[0][0]} vs ${fixtures[0][1]} locks at kickoff.`;
    }

    elements.fixtureList.innerHTML = fixtures.map(([home, away, date, time, featured]) => `
        <div class="fixture-card">
            <div class="fixture-match">
                <strong>${home} vs ${away}</strong>
                <span class="fixture-meta">${date} · ${time}</span>
            </div>
            ${featured ? '<span class="tag">Featured</span>' : '<span class="tag">League</span>'}
            <button class="predict-button" type="button">Predict</button>
        </div>
    `).join("");
}

function renderLeaderboards() {
    const rows = sampleUsers.map((user) => ({
        ...user,
        avg: user.points / user.predictions
    }));

    if (state.ranking === "average") {
        rows.sort((a, b) => {
            const aQualified = a.predictions >= state.minimumPredictions;
            const bQualified = b.predictions >= state.minimumPredictions;
            if (aQualified !== bQualified) {
                return aQualified ? -1 : 1;
            }
            return b.avg - a.avg || b.exact - a.exact || b.points - a.points;
        });
        elements.mainRankingTitle.textContent = `Ranked by average points, minimum ${state.minimumPredictions} predictions`;
    } else {
        rows.sort((a, b) => b.points - a.points || b.exact - a.exact || b.avg - a.avg);
        elements.mainRankingTitle.textContent = "Ranked by total points";
    }

    elements.leaderboardRows.innerHTML = rows.map((user, index) => `
        <tr>
            <td data-label="Rank">${index + 1}</td>
            <td>${user.name}</td>
            <td>${user.predictions}</td>
            <td>${user.exact}</td>
            <td><strong>${user.points}</strong></td>
            <td>${user.avg.toFixed(1)}</td>
        </tr>
    `).join("");

    const clubs = {};
    sampleUsers.forEach((user) => {
        if (!clubs[user.club]) {
            clubs[user.club] = { points: 0, predictions: 0, users: 0 };
        }
        clubs[user.club].points += user.points;
        clubs[user.club].predictions += user.predictions;
        clubs[user.club].users += 1;
    });

    const clubRows = Object.entries(clubs)
        .map(([club, data]) => ({
            club,
            users: data.users,
            avg: data.points / data.predictions
        }))
        .sort((a, b) => b.avg - a.avg);

    elements.clubLeaderboard.innerHTML = clubRows.map((row) => `
        <div>
            <span>${row.club} supporters · ${row.users} user${row.users > 1 ? "s" : ""}</span>
            <strong>${row.avg.toFixed(1)} avg</strong>
        </div>
    `).join("");
}

function flashButton(button, text) {
    const original = button.textContent;
    button.textContent = text;
    setTimeout(() => {
        button.textContent = original;
    }, 1100);
}
