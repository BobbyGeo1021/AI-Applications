import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import numpy as np
import time

# Configuration
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
TOURNAMENT_NAME = "IGNITE 2025"

# Initialize database
def init_database():
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            matches_played INTEGER DEFAULT 0,
            goals_for INTEGER DEFAULT 0,
            goals_against INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY,
            match_name TEXT,
            team1 TEXT,
            team2 TEXT,
            score1 INTEGER,
            score2 INTEGER,
            completed BOOLEAN DEFAULT FALSE,
            match_order INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knockout_matches (
            id INTEGER PRIMARY KEY,
            match_name TEXT,
            team1 TEXT,
            team2 TEXT,
            score1 INTEGER,
            score2 INTEGER,
            completed BOOLEAN DEFAULT FALSE,
            stage TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

# Database functions
def get_teams():
    conn = sqlite3.connect('tournament.db')
    df = pd.read_sql_query("SELECT * FROM teams ORDER BY points DESC, (goals_for - goals_against) DESC, goals_for DESC", conn)
    conn.close()
    return df

def get_matches():
    conn = sqlite3.connect('tournament.db')
    df = pd.read_sql_query("SELECT * FROM matches ORDER BY match_order", conn)
    conn.close()
    return df

def get_knockout_matches():
    conn = sqlite3.connect('tournament.db')
    df = pd.read_sql_query("SELECT * FROM knockout_matches ORDER BY stage", conn)
    conn.close()
    return df

def clear_all_data():
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    
    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    table_names = [row[0] for row in cursor.fetchall()]
    
    # Disable foreign key checks
    cursor.execute("PRAGMA foreign_keys = OFF;")
    
    # Truncate all tables
    for table in table_names:
        cursor.execute(f"DELETE FROM {table};")
    
    # Re-enable foreign key checks
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    conn.commit()
    conn.close()

def import_fixtures_from_excel(uploaded_file):
    try:
        # Check if already processed
        if st.session_state.get('file_processed', False):
            return True, "File already processed"
        
        df = pd.read_excel(uploaded_file)
        
        # Check required columns
        required_cols = ['Match', 'Team 1', 'Team 2']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return False, f"Missing columns: {', '.join(missing_cols)}"
        
        # Clean data
        df = df.dropna(subset=required_cols)
        df['Team 1'] = df['Team 1'].str.strip()
        df['Team 2'] = df['Team 2'].str.strip()
        df['Match'] = df['Match'].str.strip()
        
        # Clear existing data
        clear_all_data()
        
        conn = sqlite3.connect('tournament.db')
        cursor = conn.cursor()
        
        # Extract unique teams
        teams = set()
        for _, row in df.iterrows():
            teams.add(row['Team 1'])
            teams.add(row['Team 2'])
        
        # Insert teams
        for team in teams:
            cursor.execute("INSERT OR IGNORE INTO teams (name) VALUES (?)", (team,))
        
        # Insert matches
        for i, row in df.iterrows():
            cursor.execute('''
                INSERT INTO matches (match_name, team1, team2, match_order)
                VALUES (?, ?, ?, ?)
            ''', (row['Match'], row['Team 1'], row['Team 2'], i + 1))
        
        conn.commit()
        conn.close()
        
        # Mark as processed
        st.session_state.file_processed = True
        return True, f"Successfully imported {len(df)} matches with {len(teams)} teams!"
    
    except Exception as e:
        return False, f"Error importing fixtures: {str(e)}"

def update_match_score(match_id, score1, score2):
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    
    # Get match details
    cursor.execute("SELECT team1, team2, completed FROM matches WHERE id = ?", (match_id,))
    match_data = cursor.fetchone()
    
    if not match_data:
        conn.close()
        return False
    
    team1, team2, was_completed = match_data
    
    # If match was already completed, reverse the previous scores
    if was_completed:
        cursor.execute("SELECT score1, score2 FROM matches WHERE id = ?", (match_id,))
        old_scores = cursor.fetchone()
        if old_scores:
            old_score1, old_score2 = old_scores
            # Reverse previous stats
            update_team_stats(cursor, team1, -old_score1, -old_score2, -get_points(old_score1, old_score2), -1)
            update_team_stats(cursor, team2, -old_score2, -old_score1, -get_points(old_score2, old_score1), -1)
    
    # Update match
    cursor.execute('''
        UPDATE matches SET score1 = ?, score2 = ?, completed = TRUE WHERE id = ?
    ''', (score1, score2, match_id))
    
    # Update team stats
    update_team_stats(cursor, team1, score1, score2, get_points(score1, score2), 1)
    update_team_stats(cursor, team2, score2, score1, get_points(score2, score1), 1)
    
    conn.commit()
    conn.close()
    return True

def update_team_stats(cursor, team_name, goals_for, goals_against, points, matches_played):
    cursor.execute('''
        UPDATE teams SET 
            goals_for = goals_for + ?,
            goals_against = goals_against + ?,
            points = points + ?,
            matches_played = matches_played + ?
        WHERE name = ?
    ''', (goals_for, goals_against, points, matches_played, team_name))

def get_points(score1, score2):
    if score1 > score2:
        return 3
    elif score1 == score2:
        return 1
    else:
        return 0

def get_top_4_teams():
    teams_df = get_teams()
    return teams_df.head(4)

def generate_knockout_bracket():
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    
    # Clear existing knockout matches
    cursor.execute("DELETE FROM knockout_matches")
    
    top_4 = get_top_4_teams()
    
    if len(top_4) >= 4:
        # Semi-finals: 1st vs 4th, 2nd vs 3rd
        cursor.execute('''
            INSERT INTO knockout_matches (match_name, team1, team2, stage)
            VALUES (?, ?, ?, ?)
        ''', ("Semi-Final 1", top_4.iloc[0]['name'], top_4.iloc[3]['name'], "semi"))
        
        cursor.execute('''
            INSERT INTO knockout_matches (match_name, team1, team2, stage)
            VALUES (?, ?, ?, ?)
        ''', ("Semi-Final 2", top_4.iloc[1]['name'], top_4.iloc[2]['name'], "semi"))
        
        # Final (TBD until semis are completed)
        cursor.execute('''
            INSERT INTO knockout_matches (match_name, team1, team2, stage)
            VALUES (?, ?, ?, ?)
        ''', ("Final", "TBD", "TBD", "final"))
    
    conn.commit()
    conn.close()

def get_tournament_progress():
    matches_df = get_matches()
    if len(matches_df) == 0:
        return 0
    completed = len(matches_df[matches_df['completed'] == True])
    return (completed / len(matches_df)) * 100

def update_knockout_match_score(match_id, score1, score2):
    conn = sqlite3.connect('tournament.db')
    cursor = conn.cursor()
    
    # Update knockout match
    cursor.execute('''
        UPDATE knockout_matches SET score1 = ?, score2 = ?, completed = TRUE WHERE id = ?
    ''', (score1, score2, match_id))
    
    # Get match details to determine winner
    cursor.execute("SELECT match_name, team1, team2, stage FROM knockout_matches WHERE id = ?", (match_id,))
    match_data = cursor.fetchone()
    
    if match_data:
        match_name, team1, team2, stage = match_data
        winner = team1 if score1 > score2 else team2
        
        # Update final if this is a semi-final
        if stage == "semi":
            cursor.execute("SELECT COUNT(*) FROM knockout_matches WHERE stage = 'semi' AND completed = TRUE")
            completed_semis = cursor.fetchone()[0]
            
            if completed_semis == 2:
                # Both semis completed, update final
                cursor.execute('''
                    SELECT team1, team2, score1, score2 FROM knockout_matches 
                    WHERE stage = 'semi' AND completed = TRUE
                ''')
                semi_results = cursor.fetchall()
                
                finalists = []
                for team1, team2, s1, s2 in semi_results:
                    finalists.append(team1 if s1 > s2 else team2)
                
                if len(finalists) == 2:
                    cursor.execute('''
                        UPDATE knockout_matches SET team1 = ?, team2 = ? WHERE stage = 'final'
                    ''', (finalists[0], finalists[1]))
    
    conn.commit()
    conn.close()
    return True

# Streamlit app
def main():
    st.set_page_config(
        page_title=TOURNAMENT_NAME,
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Enhanced Football Theme CSS
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1B5E20 0%, #2E7D32 50%, #43A047 100%);
        padding: 2.5rem;
        border-radius: 20px;
        text-align: center;
        color: white;
        font-size: 3.5rem;
        font-weight: 800;
        margin-bottom: 2rem;
        box-shadow: 0 10px 40px rgba(27, 94, 32, 0.3);
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        position: relative;
        overflow: hidden;
    }
    
    .main-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
        animation: shine 3s infinite;
    }
    
    @keyframes shine {
        0% { left: -100%; }
        100% { left: 100%; }
    }
    
    .tournament-container {
        background: linear-gradient(135deg, #F1F8E9 0%, #E8F5E8 100%);
        padding: 2rem;
        border-radius: 20px;
        border: 2px solid #4CAF50;
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(76, 175, 80, 0.15);
        position: relative;
    }
    
    .scoreboard-tile {
        background: linear-gradient(135deg, #FFFFFF 0%, #F5F5F5 100%);
        padding: 1.5rem;
        border-radius: 15px;
        border-left: 6px solid #4CAF50;
        margin: 1rem 0;
        box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        position: relative;
    }
    
    .scoreboard-tile:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        border-left-color: #66BB6A;
    }
    
    .team-position {
        display: inline-block;
        width: 40px;
        height: 40px;
        border-radius: 50%;
        line-height: 40px;
        text-align: center;
        color: white;
        font-weight: bold;
        font-size: 1.2rem;
        margin-right: 1rem;
    }
    
    .position-1 { background: linear-gradient(135deg, #FFD700 0%, #FFA000 100%); }
    .position-2 { background: linear-gradient(135deg, #C0C0C0 0%, #9E9E9E 100%); }
    .position-3 { background: linear-gradient(135deg, #CD7F32 0%, #8D6E63 100%); }
    .position-4 { background: linear-gradient(135deg, #81C784 0%, #66BB6A 100%); }
    .position-other { background: linear-gradient(135deg, #90A4AE 0%, #607D8B 100%); }
    
    .match-fixture {
        background: linear-gradient(135deg, #FFFFFF 0%, #FAFAFA 100%);
        padding: 1.5rem;
        border-radius: 15px;
        border: 2px solid #E0E0E0;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        transition: all 0.3s ease;
    }
    
    .match-fixture:hover {
        border-color: #4CAF50;
        transform: translateY(-2px);
    }
    
    .match-completed {
        border-color: #4CAF50;
        background: linear-gradient(135deg, #E8F5E8 0%, #F1F8E9 100%);
    }
    
    .match-pending {
        border-color: #FF9800;
        background: linear-gradient(135deg, #FFF3E0 0%, #FFE0B2 100%);
    }
    
    .bracket-container {
        background: linear-gradient(135deg, #E8F5E8 0%, #F1F8E9 100%);
        padding: 3rem;
        border-radius: 25px;
        border: 3px solid #4CAF50;
        margin: 2rem 0;
        box-shadow: 0 12px 40px rgba(76, 175, 80, 0.2);
    }
    
    .bracket-match {
        background: linear-gradient(135deg, #FFFFFF 0%, #F5F5F5 100%);
        padding: 2rem;
        border-radius: 20px;
        border: 3px solid #4CAF50;
        text-align: center;
        font-weight: 600;
        font-size: 1.1rem;
        margin: 1rem;
        box-shadow: 0 6px 25px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        min-height: 120px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    .bracket-match:hover {
        transform: scale(1.05);
        border-color: #66BB6A;
    }
    
    .bracket-final {
        background: linear-gradient(135deg, #FFD700 0%, #FFA000 100%);
        border-color: #FF8F00;
        color: #1B5E20;
        font-weight: 800;
    }
    
    .bracket-semi {
        background: linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%);
        border-color: #2196F3;
    }
    
    .stats-card {
        background: linear-gradient(135deg, #FFFFFF 0%, #F8F9FA 100%);
        padding: 1.5rem;
        border-radius: 15px;
        border: 2px solid #4CAF50;
        text-align: center;
        box-shadow: 0 5px 20px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
    
    .admin-panel {
        background: linear-gradient(135deg, #FFF3E0 0%, #FFE0B2 100%);
        padding: 2rem;
        border-radius: 20px;
        border: 2px solid #FF9800;
        margin: 2rem 0;
        box-shadow: 0 8px 25px rgba(255, 152, 0, 0.15);
    }
    

    
    .stButton > button {
        background: linear-gradient(135deg, #4CAF50 0%, #66BB6A 100%);
        color: white;
        border: none;
        border-radius: 12px;
        font-weight: 600;
        padding: 0.75rem 2rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #66BB6A 0%, #4CAF50 100%);
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(76, 175, 80, 0.4);
    }
    
    .connection-line {
        position: absolute;
        background: linear-gradient(135deg, #4CAF50 0%, #66BB6A 100%);
        height: 4px;
        border-radius: 2px;
        box-shadow: 0 2px 8px rgba(76, 175, 80, 0.3);
    }
    
    .floating-animation {
        animation: float 4s ease-in-out infinite;
    }
    
    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-8px); }
    }
    
    .pulse-animation {
        animation: pulse 2s ease-in-out infinite;
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize database
    init_database()
    
    # Header
    st.markdown("""
<style>
.main-header {
    font-size: 36px;
    text-align: center;
    font-weight: bold;
    padding: 10px;
    margin-top: 30px;
    border: 4px solid orange;
    border-radius: 7px;
    position: relative;
    background: black;
    color: white;
    box-shadow: 0 0 25px red;
    animation: pulse 1.5s infinite alternate;
    width: 90%;  /* Set container width */
    max-width: 400px;  /* Maximum width */
    margin-left: auto;
    margin-right: auto;
    height: auto;  /* Adjust height automatically */
                
}

.floating-animation {
    animation: float 3s ease-in-out infinite;
}


.main-header::before {
    left: -30px;
}

.main-header::after {
    right: -30px;
}

@keyframes pulse {
    0% { box-shadow: 0 0 10px red; }
    100% { box-shadow: 0 0 30px orange; }
}

@keyframes flicker {
    0% { opacity: 0.7; transform: translateY(-50%) scale(1); }
    100% { opacity: 1; transform: translateY(-52%) scale(1.2); }
}

@keyframes float {
    0% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
    100% { transform: translateY(0); }
}
</style>
""", unsafe_allow_html=True)
    import base64
    def img_to_base64(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    #st.markdown(f'<div class="main-header floating-animation">⚽🔥 {TOURNAMENT_NAME} 🔥⚽</div>', unsafe_allow_html=True)
    image_path = "assets/logo.png"  # Update this path to your image location
    img_base64 = img_to_base64(image_path)

    st.markdown(f'''
<div class="main-header floating-animation">
    <img src="data:image/png;base64,{img_base64}" alt="Tournament Logo" 
        style="width: 90%; height: auto; display: block; margin: 0 auto; object-fit: contain;">
</div>
''', unsafe_allow_html=True)
    # Progress indicator
    progress = get_tournament_progress()
    st.markdown('<div class="progress-bar">', unsafe_allow_html=True)
    st.subheader("🏆 Tournament Progress")
    st.progress(progress / 100)
    st.write(f"**{progress:.1f}% Complete**")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("🏆 Tournament Menu")
    
    
    # Admin login
    if 'admin_logged_in' not in st.session_state:
        st.session_state.admin_logged_in = False
    
    if not st.session_state.admin_logged_in:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔐 Admin Login")
        password = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login", type="primary"):
            if password == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.sidebar.success("Logged in as Admin!")
                st.rerun()
            else:
                st.sidebar.error("Invalid password!")
    else:
        st.sidebar.success("✅ Admin Mode Active")
        if st.sidebar.button("Logout", type="secondary"):
            st.session_state.admin_logged_in = False
            st.rerun()
    
    # Navigation
    st.sidebar.markdown("---")
    page = st.sidebar.selectbox(
        "📍 Navigate to:",
        ["🏆 Scoreboard", "📅 Fixtures", "🎯 Knockout Bracket"],
        index=0
    )
    
    # Admin file upload
    if st.session_state.admin_logged_in:
        st.sidebar.markdown("---")
        st.sidebar.subheader("📁 Upload Fixtures")
        uploaded_file = st.sidebar.file_uploader("Choose Excel file", type=['xlsx', 'xls'])
        if uploaded_file is not None:
            success, message = import_fixtures_from_excel(uploaded_file)
            if success:
                st.sidebar.success(message)
            else:
                st.sidebar.error(message)
                st.session_state.file_processed = False
    if st.session_state.admin_logged_in:
        admin_clear_all_data()
    
    # Route to pages
    if page == "🏆 Scoreboard":
        show_scoreboard()
    elif page == "📅 Fixtures":
        show_fixtures()
    elif page == "🎯 Knockout Bracket":
        show_knockout_bracket()

def show_scoreboard():
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("📊 League Table")
        
        teams_df = get_teams()
        
        if not teams_df.empty:
            for i, (_, team) in enumerate(teams_df.iterrows(), 1):
                gd = team['goals_for'] - team['goals_against']
                
                # Football-themed position indicators
                if i == 1:
                    position_indicator = "👑"  # Crown for champion
                    bg_color = "#FFD700"
                    border_color = "#FFA000"
                elif i == 2:
                    position_indicator = "🥈"  # Silver medal
                    bg_color = "#E8F5E8"
                    border_color = "#4CAF50"
                elif i == 3:
                    position_indicator = "🥉"  # Bronze medal
                    bg_color = "#E8F5E8"
                    border_color = "#4CAF50"
                elif i == 4:
                    position_indicator = "⚡"  # Lightning for European competition
                    bg_color = "#FFF3E0"
                    border_color = "#FF9800"
                elif i <= 6:
                    position_indicator = "🏆"  # Trophy for European spots
                    bg_color = "#FFF3E0"
                    border_color = "#FF9800"
                elif i <= len(teams_df) - 3:
                    position_indicator = "⚽"  # Football for safe positions
                    bg_color = "#F5F5F5"
                    border_color = "#9E9E9E"
                else:
                    position_indicator = "🔻"  # Red triangle for relegation zone
                    bg_color = "#FFEBEE"
                    border_color = "#F44336"
                
                # Goal difference color logic
                gd_color = 'green' if gd > 0 else 'red' if gd < 0 else 'orange'
                
                st.markdown(f"""
                <style>
                .scoreboard-tile-{i} {{
                    padding: 12px;
                    margin-bottom: 8px;
                    background: {bg_color}; 
                    border-radius: 10px;
                    border-left: 6px solid {border_color};
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                }}
                
                .scoreboard-content-{i} {{
                    display: flex;
                    flex-direction: column;
                }}
                
                @media (min-width: 600px) {{
                    .scoreboard-content-{i} {{
                        flex-direction: row;
                        justify-content: space-between;
                        align-items: center;
                    }}
                }}
                
                .team-info-{i} {{
                    display: flex;
                    align-items: center;
                    margin-bottom: 8px;
                }}
                
                @media (min-width: 600px) {{
                    .team-info-{i} {{
                        margin-bottom: 0;
                    }}
                }}
                
                .team-position-{i} {{
                    font-weight: bold;
                    font-size: 1rem;
                    margin-right: 8px;
                    color: #000000;
                }}
                
                .team-name-{i} {{
                    font-size: 1rem;
                    font-weight: 600;
                    color: #000;
                }}
                
                .team-stats-{i} {{
                    display: flex;
                    justify-content: space-between;
                    gap: 1rem;
                }}
                
                .stat-{i} {{
                    text-align: center;
                }}
                
                .stat-label-{i} {{
                    font-size: 0.7rem;
                    color: #000000;
                }}
                
                .stat-value-{i} {{
                    font-size: 1rem;
                    font-weight: 600;
                }}
                
                .stat-gd-{i} {{
                    color: {gd_color};
                }}
                </style>
                
                <div class="scoreboard-tile-{i}">
                    <div class="scoreboard-content-{i}">
                        <div class="team-info-{i}">
                            <span class="team-position-{i}">{i}</span>
                            <span class="team-name-{i}">{position_indicator} {team['name']}</span>
                        </div>
                        <div class="team-stats-{i}">
                            <div class="stat-{i}">
                                <div class="stat-label-{i}">Played</div>
                                <div class="stat-value-{i}" style="color:#000000;">{team['matches_played']}</div>
                            </div>
                            <div class="stat-{i}">
                                <div class="stat-label-{i}">GF</div>
                                <div class="stat-value-{i}" style="color:#000000;">{team['goals_for']}</div>
                            </div>
                            <div class="stat-{i}">
                                <div class="stat-label-{i}">GA</div>
                                <div class="stat-value-{i}" style="color:#000000;">{team['goals_against']}</div>
                            </div>
                            <div class="stat-{i}">
                                <div class="stat-label-{i}">GD</div>
                                <div class="stat-value-{i} stat-gd-{i}">{gd:+d}</div>
                            </div>
                            <div class="stat-{i}">
                                <div class="stat-label-{i}">Points</div>
                                <div class="stat-value-{i}" style="color:#1B5E20;">{team['points']}</div>
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No teams available. Please upload fixtures first.")
    
    with col2:
        st.subheader("📈 Stats")
        
        matches_df = get_matches()
        total_matches = len(matches_df)
        completed_matches = len(matches_df[matches_df['completed'] == True])
        
        st.markdown(f'''
        <div style="
            background: linear-gradient(135deg, #2196F3, #21CBF3); 
            padding: 15px; 
            border-radius: 12px; 
            margin: 10px 0;
            box-shadow: 0 3px 6px rgba(0,0,0,0.15);
        ">
            <div style="font-weight: bold; font-size: 1rem; color: #fff; margin-bottom: 8px;">📊 MATCHES</div>
            <div style="font-size: 0.9rem; color: #fff; font-weight: 600; line-height: 1.5;">
                TOTAL: <span style="font-size: 1.1rem; font-weight: bold;">{total_matches}</span><br>
                DONE: <span style="font-size: 1.1rem; font-weight: bold;">{completed_matches}</span><br>
                LEFT: <span style="font-size: 1.1rem; font-weight: bold;">{total_matches - completed_matches}</span>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        if not teams_df.empty:
            top_team = teams_df.iloc[0]
            st.markdown(f'''
            <div style="
                background: linear-gradient(135deg, #FF6B35, #F7931E); 
                padding: 15px; 
                border-radius: 12px; 
                margin: 10px 0;
                box-shadow: 0 3px 6px rgba(0,0,0,0.15);
            ">
                <div style="font-weight: bold; font-size: 1rem; color: #fff; margin-bottom: 8px;">🏆 LEADER</div>
                <div style="font-size: 0.9rem; color: #fff; font-weight: 600; line-height: 1.5;">
                    <div style="font-size: 1.1rem; font-weight: bold; margin-bottom: 4px;">{top_team['name']}</div>
                    POINTS: <span style="font-size: 1.2rem; font-weight: bold;">{top_team['points']}</span><br>
                    GOALS: <span style="font-size: 1.1rem; font-weight: bold;">{top_team['goals_for']}</span><br>
                    GD: <span style="font-size: 1.1rem; font-weight: bold;">{top_team['goals_for'] - top_team['goals_against']:+d}</span>
                </div>
            </div>
            ''', unsafe_allow_html=True)

def show_fixtures():
    #st.markdown('<div class="tournament-container">', unsafe_allow_html=True)
    st.subheader("📅 Match Fixtures")
    
    matches_df = get_matches()
    
    if matches_df.empty:
        st.warning("No fixtures available. Please upload an Excel file with fixtures.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    if st.session_state.admin_logged_in:
        st.info("🔧 Admin Mode: Update match scores")
        
        for _, match in matches_df.iterrows():
            status = "✅ Completed" if match['completed'] else "⏳ Pending"
            
            with st.expander(f"{match['match_name']}: {match['team1']} vs {match['team2']} - {status}", 
                           expanded=not match['completed']):
                
                # Mobile-optimized layout: Stack vertically instead of side-by-side
                st.markdown(f"**🏠 {match['team1']}**")
                score1 = st.number_input("Goals", 
                                       min_value=0, max_value=20, 
                                       value=int(match['score1']) if match['completed'] else 0,
                                       key=f"score1_{match['id']}")
                
                st.markdown("**VS**")
                
                st.markdown(f"**🚌 {match['team2']}**")
                score2 = st.number_input("Goals", 
                                       min_value=0, max_value=20, 
                                       value=int(match['score2']) if match['completed'] else 0,
                                       key=f"score2_{match['id']}")
                
                if st.button("Update Match", key=f"update_{match['id']}", type="primary", use_container_width=True):
                    if update_match_score(match['id'], score1, score2):
                        st.success("Updated!")
                        st.rerun()
                
                if match['completed']:
                    winner = match['team1'] if match['score1'] > match['score2'] else match['team2'] if match['score2'] > match['score1'] else "Draw"
                    st.success(f"🏆 Final: {match['team1']} {int(match['score1'])} - {int(match['score2'])} {match['team2']} ({winner})")
    else:
        # Read-only view - Mobile optimized
        completed_matches = matches_df[matches_df['completed'] == True]
        pending_matches = matches_df[matches_df['completed'] == False]
        
        if not completed_matches.empty:
            st.subheader("✅ Completed Matches")
            for _, match in completed_matches.iterrows():
                result_emoji = "🏆" if match['score1'] != match['score2'] else "🤝"
                st.markdown(f'''
                <div style="background: #E8F5E8; border-radius: 8px; padding: 8px; margin: 4px 0; border-left: 3px solid #4CAF50;">
                    <div style="font-size: 0.8rem; color: #000000; text-align: center; margin-bottom: 4px;">{match['match_name']}</div>
                    <div style="text-align: center; font-size: 0.9rem;color: #000000;">
                        {match['team1']} <strong><span style="margin: 0 9px;">{int(match['score1'])} - {int(match['score2'])}</span></strong> {match['team2']} {result_emoji}
                    </div>
                </div>
                ''', unsafe_allow_html=True)
        
        if not pending_matches.empty:
            st.subheader("⏳ Upcoming Matches")
            for _, match in pending_matches.iterrows():
                st.markdown(f'''
                <div style="background: #FFF3E0; border-radius: 8px; padding: 8px; margin: 4px 0; border-left: 3px solid #FF9800;">
                    <div style="font-size: 0.8rem; color: #000000; text-align: center; margin-bottom: 4px;">{match['match_name']}</div>
                    <div style="text-align: center; font-size: 0.9rem;color: #000000;">
                        {match['team1']}  <strong><span style="color: #FF9800; margin: 0 7px;">  vs  </span></strong>  {match['team2']} ⏳
                    </div>
                </div>
                ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
import os
import base64
# Complete the missing show_knockout_bracket function

import os
import base64
import logging
from pathlib import Path
import streamlit as st

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_team_logo_base64(team_name):
    """
    Get team logo as base64 string with comprehensive logging and fallback options.
    """
    # Get the current working directory and script directory
    current_dir = os.getcwd()
    script_dir = Path(__file__).parent if '__file__' in globals() else Path('.')
    
    logger.info(f"Current working directory: {current_dir}")
    logger.info(f"Script directory: {script_dir}")
    
    # Multiple possible paths to check
    possible_paths = [
        # Relative to current working directory
        Path(current_dir) / "team_logo" / f"{team_name}.png",
        Path(current_dir) / "team_logo" / f"{team_name}.jpg",
        # Relative to script directory
        script_dir / "team_logo" / f"{team_name}.png",
        script_dir / "team_logo" / f"{team_name}.jpg",
        # Direct relative paths
        Path("team_logo") / f"{team_name}.png",
        Path("team_logo") / f"{team_name}.jpg",
        # Absolute paths (if team_logo is in root)
        Path(".") / "team_logo" / f"{team_name}.png",
        Path(".") / "team_logo" / f"{team_name}.jpg",
    ]
    
    logger.info(f"Searching for logo for team: {team_name}")
    
    # List all files in team_logo directory if it exists
    team_logo_dirs = [
        Path(current_dir) / "team_logo",
        script_dir / "team_logo",
        Path("team_logo"),
        Path(".") / "team_logo"
    ]
    
    for logo_dir in team_logo_dirs:
        if logo_dir.exists():
            logger.info(f"Found team_logo directory: {logo_dir}")
            try:
                files = list(logo_dir.glob("*"))
                logger.info(f"Files in {logo_dir}: {[f.name for f in files]}")
            except Exception as e:
                logger.error(f"Error listing files in {logo_dir}: {e}")
        else:
            logger.info(f"Directory does not exist: {logo_dir}")
    
    # Try each possible path
    for path in possible_paths:
        logger.info(f"Checking path: {path}")
        try:
            if path.exists() and path.is_file():
                logger.info(f"Found logo at: {path}")
                with open(path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode()
                    return f'<img src="data:image/png;base64,{encoded}" class="team-logo">'
            else:
                logger.info(f"Path does not exist or is not a file: {path}")
        except Exception as e:
            logger.error(f"Error reading {path}: {e}")
    
    # If no logo found, return placeholder
    logger.warning(f"No logo found for team: {team_name}")
    return '<div class="placeholder-logo">🏆</div>'

def show_knockout_bracket():
    st.subheader("🎯 Knockout Bracket")
    
    # Add debug information for admins
    if st.session_state.get('admin_logged_in', False):
        with st.expander("🔍 Debug Information"):
            st.write("**Current Working Directory:**", os.getcwd())
            st.write("**Script Directory:**", str(Path(__file__).parent if '__file__' in globals() else "Unknown"))
            
            # Check if team_logo directory exists
            possible_dirs = [
                Path(os.getcwd()) / "team_logo",
                Path("team_logo"),
                Path(".") / "team_logo"
            ]
            
            for dir_path in possible_dirs:
                if dir_path.exists():
                    st.write(f"**Found team_logo at:** {dir_path}")
                    try:
                        files = list(dir_path.glob("*"))
                        st.write(f"**Files:** {[f.name for f in files]}")
                    except Exception as e:
                        st.write(f"**Error listing files:** {e}")
                    break
            else:
                st.warning("team_logo directory not found in any expected location")
    
    # Streamlined CSS with horizontal layout
    st.markdown("""
    <style>

    .bracket-layout {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 3rem;
        flex-wrap: wrap;
    }
    
    .semi-finals {
        display: flex;
        flex-direction: row;
        gap: 4rem;
    }
    
    .match-box {
        background: rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        min-width: 280px;
        border: 2px solid rgba(255,255,255,0.1);
        margin-bottom: 2rem;
    }
    
    .final-box {
        background: linear-gradient(145deg, #dc143c, #ff1744);
        border: 3px solid #ff4444;
        box-shadow: 0 0 25px rgba(220, 20, 60, 0.7);
        min-width: 280px;
    }
    
    .final-box:hover {
        box-shadow: 0 0 40px rgba(220, 20, 60, 0.9);
    }
    
    .match-title {
        color: white;
        font-weight: bold;
        text-align: center;
        margin-bottom: 1.5rem;
        font-size: 1.2rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
    }
    
    .teams-container {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-bottom: 1rem;
        gap: 2rem;
    }
    
    .team-section {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.5rem;
    }
    
    .team-logo {
        width: 100px;
        height: 100px;
        border-radius: 8px;
        border: 2px solid rgba(255,255,255,0.2);
        object-fit: cover;
    }
    
    .team-name {
        color: white;
        font-weight: bold;
        font-size: 1rem;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.7);
    }
    
    .scores-row {
        display: flex;
        justify-content: center;
        gap: 4rem;
        margin-top: 1rem;
    }
    
    .vs-divider {
        color: #ffd700;
        font-weight: bold;
        font-size: 1.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.7);
        align-self: center;
        margin: 0 1rem;
    }
    
    .connector {
        color: #ffd700;
        font-size: 3rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.7);
        margin: 0 1rem;
    }
    
    .champion-banner {
        text-align: center;
        margin-top: 2rem;
        background: linear-gradient(135deg, #ffd700 0%, #ffb300 100%);
        padding: 2rem;
        border-radius: 20px;
        border: 3px solid #ff8c00;
        box-shadow: 0 0 30px rgba(255, 215, 0, 0.8);
    }
    
    .placeholder-logo {
        width: 100px;
        height: 100px;
        background: rgba(255,255,255,0.1);
        border: 2px dashed rgba(255,255,255,0.3);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
    }
    
    .team-score {
        color: #ffd700;
        font-weight: bold;
        font-size: 1.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.7);
        background: rgba(0,0,0,0.3);
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        min-width: 40px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Check if league stage is complete
    matches_df = get_matches()
    if matches_df.empty or len(matches_df[matches_df['completed'] == True]) < len(matches_df) * 0.8:
        st.warning("⚠️ Complete more league matches to generate knockout bracket")
        return
    
    # Generate bracket button (admin only)
    if st.session_state.get('admin_logged_in', False):
        if st.button("🔄 Generate Knockout Bracket", type="primary"):
            generate_knockout_bracket()
            st.success("Knockout bracket generated!")
            st.rerun()
    
    knockout_df = get_knockout_matches()
    if knockout_df.empty:
        st.info("No knockout matches generated yet.")
        return
    
    # Display bracket
    st.markdown('<div class="bracket-layout">', unsafe_allow_html=True)
    
    # Semi-finals
    st.markdown('<div class="semi-finals">', unsafe_allow_html=True)
    
    semis = knockout_df[knockout_df['stage'] == 'semi'].sort_values('id')
    for i, (_, match) in enumerate(semis.iterrows()):
        status = "✅" if match['completed'] else "⏳"
        
        # Get team logos using the new function
        team1_logo = get_team_logo_base64(match['team1'])
        team2_logo = get_team_logo_base64(match['team2'])
        
        # Single markdown with complete HTML structure
        st.markdown(f'''
        <div class="match-box">
            <div class="match-title">Semi-Final {i+1} {status}</div>
            <div class="teams-container">
                <div class="team-section">
                    {team1_logo}
                    <div class="team-name">{match["team1"]}</div>
                </div>
                <div class="vs-divider">VS</div>
                <div class="team-section">
                    {team2_logo}
                    <div class="team-name">{match["team2"]}</div>
                </div>
            </div>
            <div class="scores-row">
                <div class="team-score">{"-" if not match['completed'] else int(match["score1"])}</div>
                <div class="team-score">{"-" if not match['completed'] else int(match["score2"])}</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Admin score update
        if st.session_state.get('admin_logged_in', False) and not match['completed']:
            with st.expander(f"📝 Update SF{i+1} Score"):
                col_a, col_b = st.columns(2)
                with col_a:
                    s1 = st.number_input(f"{match['team1']} Goals", 0, 20, key=f"ko_s1_{match['id']}")
                with col_b:
                    s2 = st.number_input(f"{match['team2']} Goals", 0, 20, key=f"ko_s2_{match['id']}")
                
                if st.button("Update Score", key=f"ko_update_{match['id']}", type="primary"):
                    update_knockout_match_score(match['id'], s1, s2)
                    st.success("Score updated!")
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close semi-finals
    
    # Connector
    st.markdown('<div class="connector">➤</div>', unsafe_allow_html=True)
    
    # Final
    final = knockout_df[knockout_df['stage'] == 'final']
    if not final.empty:
        final_match = final.iloc[0]
        status = "🏆" if final_match['completed'] else "⏳"
        
        st.markdown(f'''
        <div class="match-box final-box">
            <div class="match-title">FINAL {status}</div>
        ''', unsafe_allow_html=True)
        
        if final_match['team1'] == 'TBD':
            st.markdown('<div style="text-align: center; color: white; padding: 2rem;">Awaiting Semi-Final Results</div>', unsafe_allow_html=True)
        else:
            # Get final team logos using the new function
            final_team1_logo = get_team_logo_base64(final_match['team1'])
            final_team2_logo = get_team_logo_base64(final_match['team2'])
            
            # Single markdown for final
            st.markdown(f'''
            <div class="teams-container">
                <div class="team-section">
                    {final_team1_logo}
                    <div class="team-name">{final_match["team1"]}</div>
                </div>
                <div class="vs-divider">VS</div>
                <div class="team-section">
                    {final_team2_logo}
                    <div class="team-name">{final_match["team2"]}</div>
                </div>
            </div>
            <div class="scores-row">
                <div class="team-score">{"-" if not final_match['completed'] else int(final_match["score1"])}</div>
                <div class="team-score">{"-" if not final_match['completed'] else int(final_match["score2"])}</div>
            </div>
            ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)  # Close final match-box
        
        # Admin final score update
        if st.session_state.get('admin_logged_in', False) and not final_match['completed'] and final_match['team1'] != 'TBD':
            with st.expander("📝 Update Final Score"):
                col_a, col_b = st.columns(2)
                with col_a:
                    f1 = st.number_input(f"{final_match['team1']} Goals", 0, 20, key=f"final_s1_{final_match['id']}")
                with col_b:
                    f2 = st.number_input(f"{final_match['team2']} Goals", 0, 20, key=f"final_s2_{final_match['id']}")
                
                if st.button("Update Final Score", key=f"final_update_{final_match['id']}", type="primary"):
                    update_knockout_match_score(final_match['id'], f1, f2)
                    st.success("Final score updated!")
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close bracket-layout
    
    # Champion display
    if not final.empty and final.iloc[0]['completed']:
        final_match = final.iloc[0]
        winner = final_match['team1'] if final_match['score1'] > final_match['score2'] else final_match['team2']
        
        st.markdown(f'''
        <div class="champion-banner">
            <h1 style="color: #8B0000; font-size: 2.5rem; margin: 0;">🏆 CHAMPION 🏆</h1>
            <h2 style="color: #8B0000; font-size: 2rem; margin: 1rem 0;">{winner}</h2>
        </div>
        ''', unsafe_allow_html=True)

# Alternative method using st.image (add this as a backup option)
def show_knockout_bracket_alt():
    """
    Alternative version using Streamlit's st.image instead of base64 embedding.
    This might work better in some deployment environments.
    """
    st.subheader("🎯 Knockout Bracket (Alternative)")
    
    # Check if league stage is complete
    matches_df = get_matches()
    if matches_df.empty or len(matches_df[matches_df['completed'] == True]) < len(matches_df) * 0.8:
        st.warning("⚠️ Complete more league matches to generate knockout bracket")
        return
    
    knockout_df = get_knockout_matches()
    if knockout_df.empty:
        st.info("No knockout matches generated yet.")
        return
    
    # Semi-finals using columns and st.image
    st.subheader("Semi-Finals")
    
    semis = knockout_df[knockout_df['stage'] == 'semi'].sort_values('id')
    for i, (_, match) in enumerate(semis.iterrows()):
        st.write(f"**Semi-Final {i+1}** {'✅' if match['completed'] else '⏳'}")
        
        col1, col2, col3 = st.columns([2, 1, 2])
        
        with col1:
            # Try to display team 1 logo
            logo_paths = [
                f"team_logo/{match['team1'].lower()}.png",
                f"team_logo/{match['team1'].lower()}.jpg",
                f"./team_logo/{match['team1'].lower()}.png",
                f"./team_logo/{match['team1'].lower()}.jpg"
            ]
            
            logo_displayed = False
            for path in logo_paths:
                try:
                    if os.path.exists(path):
                        st.image(path, width=100)
                        logo_displayed = True
                        break
                except Exception as e:
                    logger.error(f"Error displaying image {path}: {e}")
            
            if not logo_displayed:
                st.write("🏆")  # Placeholder
            
            st.write(f"**{match['team1']}**")
            st.write(f"Score: {'-' if not match['completed'] else int(match['score1'])}")
        
        with col2:
            st.write("**VS**")
        
        with col3:
            # Try to display team 2 logo
            logo_paths = [
                f"team_logo/{match['team2'].lower()}.png",
                f"team_logo/{match['team2'].lower()}.jpg",
                f"./team_logo/{match['team2'].lower()}.png",
                f"./team_logo/{match['team2'].lower()}.jpg"
            ]
            
            logo_displayed = False
            for path in logo_paths:
                try:
                    if os.path.exists(path):
                        st.image(path, width=100)
                        logo_displayed = True
                        break
                except Exception as e:
                    logger.error(f"Error displaying image {path}: {e}")
            
            if not logo_displayed:
                st.write("🏆")  # Placeholder
            
            st.write(f"**{match['team2']}**")
            st.write(f"Score: {'-' if not match['completed'] else int(match['score2'])}")
        
        st.divider()
    
    # Final
    final = knockout_df[knockout_df['stage'] == 'final']
    if not final.empty:
        final_match = final.iloc[0]
        st.subheader(f"Final {'🏆' if final_match['completed'] else '⏳'}")
        
        if final_match['team1'] != 'TBD':
            col1, col2, col3 = st.columns([2, 1, 2])
            
            with col1:
                st.write(f"**{final_match['team1']}**")
                st.write(f"Score: {'-' if not final_match['completed'] else int(final_match['score1'])}")
            
            with col2:
                st.write("**VS**")
            
            with col3:
                st.write(f"**{final_match['team2']}**")
                st.write(f"Score: {'-' if not final_match['completed'] else int(final_match['score2'])}")
        else:
            st.info("Awaiting Semi-Final Results")
#############################################################################










def show_knockout_brackets():
    st.subheader("🎯 Knockout Bracket")
    
    # Streamlined CSS with horizontal layout
    st.markdown("""
    <style>

    .bracket-layout {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 3rem;
        flex-wrap: wrap;
    }
    
    .semi-finals {
        display: flex;
        flex-direction: row;
        gap: 4rem;
    }
    
    .match-box {
        background: rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        min-width: 280px;
        border: 2px solid rgba(255,255,255,0.1);
        margin-bottom: 2rem;
    }
    
    .final-box {
        background: linear-gradient(145deg, #dc143c, #ff1744);
        border: 3px solid #ff4444;
        box-shadow: 0 0 25px rgba(220, 20, 60, 0.7);
        min-width: 280px;
    }
    
    .final-box:hover {
        box-shadow: 0 0 40px rgba(220, 20, 60, 0.9);
    }
    
    .match-title {
        color: white;
        font-weight: bold;
        text-align: center;
        margin-bottom: 1.5rem;
        font-size: 1.2rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
    }
    
    .teams-container {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-bottom: 1rem;
        gap: 2rem;
    }
    
    .team-section {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.5rem;
    }
    
    .team-logo {
        width: 100px;
        height: 100px;
        border-radius: 8px;
        border: 2px solid rgba(255,255,255,0.2);
    }
    
    .team-name {
        color: white;
        font-weight: bold;
        font-size: 1rem;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.7);
    }
    
    .scores-row {
        display: flex;
        justify-content: center;
        gap: 4rem;
        margin-top: 1rem;
    }
    
    .vs-divider {
        color: #ffd700;
        font-weight: bold;
        font-size: 1.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.7);
        align-self: center;
        margin: 0 1rem;
    }
    
    .connector {
        color: #ffd700;
        font-size: 3rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.7);
        margin: 0 1rem;
    }
    
    .champion-banner {
        text-align: center;
        margin-top: 2rem;
        background: linear-gradient(135deg, #ffd700 0%, #ffb300 100%);
        padding: 2rem;
        border-radius: 20px;
        border: 3px solid #ff8c00;
        box-shadow: 0 0 30px rgba(255, 215, 0, 0.8);
    }
    
    .placeholder-logo {
        width: 100px;
        height: 100px;
        background: rgba(255,255,255,0.1);
        border: 2px dashed rgba(255,255,255,0.3);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
    }
    
    .team-score {
        color: #ffd700;
        font-weight: bold;
        font-size: 1.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.7);
        background: rgba(0,0,0,0.3);
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        min-width: 40px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Check if league stage is complete
    matches_df = get_matches()
    if matches_df.empty or len(matches_df[matches_df['completed'] == True]) < len(matches_df) * 0.8:
        st.warning("⚠️ Complete more league matches to generate knockout bracket")
        return
    
    # Generate bracket button (admin only)
    if st.session_state.admin_logged_in:
        if st.button("🔄 Generate Knockout Bracket", type="primary"):
            generate_knockout_bracket()
            st.success("Knockout bracket generated!")
            st.rerun()
    
    knockout_df = get_knockout_matches()
    if knockout_df.empty:
        st.info("No knockout matches generated yet.")
        return
    
    # Display bracket
    #st.markdown('<div class="bracket-container">', unsafe_allow_html=True)
    st.markdown('<div class="bracket-layout">', unsafe_allow_html=True)
    
    # Semi-finals
    st.markdown('<div class="semi-finals">', unsafe_allow_html=True)
    
    semis = knockout_df[knockout_df['stage'] == 'semi'].sort_values('id')
    for i, (_, match) in enumerate(semis.iterrows()):
        status = "✅" if match['completed'] else "⏳"
        
        # Get team logos
        logo1_path = f"team_logo/{match['team1'].lower()}.png"
        if not os.path.exists(logo1_path):
            logo1_path = f"team_logo/{match['team1'].lower()}.jpg"
        
        logo2_path = f"team_logo/{match['team2'].lower()}.png"
        if not os.path.exists(logo2_path):
            logo2_path = f"team_logo/{match['team2'].lower()}.jpg"
        
        # Team 1 logo HTML
        if os.path.exists(logo1_path):
            with open(logo1_path, "rb") as f:
                import base64
                encoded1 = base64.b64encode(f.read()).decode()
                team1_logo = f'<img src="data:image/png;base64,{encoded1}" class="team-logo">'
        else:
            team1_logo = '<div class="placeholder-logo">🏆</div>'
        
        # Team 2 logo HTML
        if os.path.exists(logo2_path):
            with open(logo2_path, "rb") as f:
                encoded2 = base64.b64encode(f.read()).decode()
                team2_logo = f'<img src="data:image/png;base64,{encoded2}" class="team-logo">'
        else:
            team2_logo = '<div class="placeholder-logo">🏆</div>'
        
        # Single markdown with complete HTML structure
        st.markdown(f'''
        <div class="match-box">
            <div class="match-title">Semi-Final {i+1} {status}</div>
            <div class="teams-container">
                <div class="team-section">
                    {team1_logo}
                    <div class="team-name">{match["team1"]}</div>
                </div>
                <div class="vs-divider">VS</div>
                <div class="team-section">
                    {team2_logo}
                    <div class="team-name">{match["team2"]}</div>
                </div>
            </div>
            <div class="scores-row">
                <div class="team-score">{"-" if not match['completed'] else int(match["score1"])}</div>
                <div class="team-score">{"-" if not match['completed'] else int(match["score2"])}</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        
        # Admin score update
        if st.session_state.admin_logged_in and not match['completed']:
            with st.expander(f"📝 Update SF{i+1} Score"):
                col_a, col_b = st.columns(2)
                with col_a:
                    s1 = st.number_input(f"{match['team1']} Goals", 0, 20, key=f"ko_s1_{match['id']}")
                with col_b:
                    s2 = st.number_input(f"{match['team2']} Goals", 0, 20, key=f"ko_s2_{match['id']}")
                
                if st.button("Update Score", key=f"ko_update_{match['id']}", type="primary"):
                    update_knockout_match_score(match['id'], s1, s2)
                    st.success("Score updated!")
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close semi-finals
    
    # Connector
    st.markdown('<div class="connector">➤</div>', unsafe_allow_html=True)
    
    # Final
    final = knockout_df[knockout_df['stage'] == 'final']
    if not final.empty:
        final_match = final.iloc[0]
        status = "🏆" if final_match['completed'] else "⏳"
        
        st.markdown(f'''
        <div class="match-box final-box">
            <div class="match-title">FINAL {status}</div>
        ''', unsafe_allow_html=True)
        
        if final_match['team1'] == 'TBD':
            st.markdown('<div style="text-align: center; color: white; padding: 2rem;">Awaiting Semi-Final Results</div>', unsafe_allow_html=True)
        else:
            # Get final team logos
            final_logo1_path = f"team_logo/{final_match['team1'].lower()}.png"
            if not os.path.exists(final_logo1_path):
                final_logo1_path = f"team_logo/{final_match['team1'].lower()}.jpg"
            
            final_logo2_path = f"team_logo/{final_match['team2'].lower()}.png"
            if not os.path.exists(final_logo2_path):
                final_logo2_path = f"team_logo/{final_match['team2'].lower()}.jpg"
            
            # Final Team 1 logo HTML
            if os.path.exists(final_logo1_path):
                with open(final_logo1_path, "rb") as f:
                    final_encoded1 = base64.b64encode(f.read()).decode()
                    final_team1_logo = f'<img src="data:image/png;base64,{final_encoded1}" class="team-logo">'
            else:
                final_team1_logo = '<div class="placeholder-logo">🏆</div>'
            
            # Final Team 2 logo HTML
            if os.path.exists(final_logo2_path):
                with open(final_logo2_path, "rb") as f:
                    final_encoded2 = base64.b64encode(f.read()).decode()
                    final_team2_logo = f'<img src="data:image/png;base64,{final_encoded2}" class="team-logo">'
            else:
                final_team2_logo = '<div class="placeholder-logo">🏆</div>'
            
            # Single markdown for final
            st.markdown(f'''
            <div class="teams-container">
                <div class="team-section">
                    {final_team1_logo}
                    <div class="team-name">{final_match["team1"]}</div>
                </div>
                <div class="vs-divider">VS</div>
                <div class="team-section">
                    {final_team2_logo}
                    <div class="team-name">{final_match["team2"]}</div>
                </div>
            </div>
            <div class="scores-row">
                <div class="team-score">{"-" if not final_match['completed'] else int(final_match["score1"])}</div>
                <div class="team-score">{"-" if not final_match['completed'] else int(final_match["score2"])}</div>
            </div>
            ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)  # Close final match-box
        
        # Admin final score update
        if st.session_state.admin_logged_in and not final_match['completed'] and final_match['team1'] != 'TBD':
            with st.expander("📝 Update Final Score"):
                col_a, col_b = st.columns(2)
                with col_a:
                    f1 = st.number_input(f"{final_match['team1']} Goals", 0, 20, key=f"final_s1_{final_match['id']}")
                with col_b:
                    f2 = st.number_input(f"{final_match['team2']} Goals", 0, 20, key=f"final_s2_{final_match['id']}")
                
                if st.button("Update Final Score", key=f"final_update_{final_match['id']}", type="primary"):
                    update_knockout_match_score(final_match['id'], f1, f2)
                    st.success("Final score updated!")
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close bracket-layout
    st.markdown('</div>', unsafe_allow_html=True)  # Close bracket-container
    
    # Champion display
    if not final.empty and final.iloc[0]['completed']:
        final_match = final.iloc[0]
        winner = final_match['team1'] if final_match['score1'] > final_match['score2'] else final_match['team2']
        
        st.markdown(f'''
        <div class="champion-banner">
            <h1 style="color: #8B0000; font-size: 2.5rem; margin: 0;">🏆 CHAMPION 🏆</h1>
            <h2 style="color: #8B0000; font-size: 2rem; margin: 1rem 0;">{winner}</h2>
        </div>
        ''', unsafe_allow_html=True)


# Enhanced import function to handle Excel better
def import_fixtures_from_excel(uploaded_file):
    try:
        # Read Excel file
        df = pd.read_excel(uploaded_file)
        
        # Check required columns
        required_cols = ['Match', 'Team 1', 'Team 2']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return False, f"Missing columns: {', '.join(missing_cols)}"
        
        # Clean data
        df = df.dropna(subset=required_cols)
        df['Team 1'] = df['Team 1'].str.strip()
        df['Team 2'] = df['Team 2'].str.strip()
        df['Match'] = df['Match'].str.strip()
        
        # Clear existing data
        clear_all_data()
        
        conn = sqlite3.connect('tournament.db')
        cursor = conn.cursor()
        
        # Extract unique teams
        teams = set()
        for _, row in df.iterrows():
            teams.add(row['Team 1'])
            teams.add(row['Team 2'])
        
        # Insert teams
        for team in teams:
            cursor.execute("INSERT OR IGNORE INTO teams (name) VALUES (?)", (team,))
        
        # Insert matches
        for i, row in df.iterrows():
            # Handle pre-filled scores if they exist
            score1 = row.get('Score1', None)
            score2 = row.get('Score2', None)
            completed = False
            
            if pd.notna(score1) and pd.notna(score2):
                score1 = int(score1)
                score2 = int(score2)
                completed = True
            else:
                score1 = score2 = None
            
            cursor.execute('''
                INSERT INTO matches (match_name, team1, team2, score1, score2, completed, match_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (row['Match'], row['Team 1'], row['Team 2'], score1, score2, completed, i + 1))
            
            # Update team stats if scores exist
            if completed:
                update_team_stats(cursor, row['Team 1'], score1, score2, get_points(score1, score2), 1)
                update_team_stats(cursor, row['Team 2'], score2, score1, get_points(score2, score1), 1)
        
        conn.commit()
        conn.close()
        return True, f"Successfully imported {len(df)} matches with {len(teams)} teams!"
    
    except Exception as e:
        return False, f"Error importing fixtures: {str(e)}"

# Add clear data function for admin

def admin_clear_all_data():
    if st.session_state.admin_logged_in:
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚠️ Danger Zone")
        
        if st.sidebar.button("🗑️ Clear All Data", type="secondary"):
            st.session_state.show_clear_confirm = True
        
        if st.session_state.get('show_clear_confirm', False):
            reset_text = st.sidebar.text_input("Type 'RESET' to confirm:", key="reset_confirm")
            if st.sidebar.button("✅ Confirm Delete", type="primary"):
                if reset_text == "RESET":
                    clear_all_data()
                    st.session_state.show_clear_confirm = False
                    st.session_state.file_processed = False  # Reset file processing flag
                    st.sidebar.success("All data cleared!")
                    st.rerun()
                else:
                    st.sidebar.error("Must type 'RESET' exactly")



if __name__ == "__main__":
    main()
