import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import numpy as np
import time

# Configuration
ADMIN_PASSWORD = "admin123"
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
    padding: 20px;
    margin-top: 30px;
    border: 4px solid orange;
    border-radius: 12px;
    position: relative;
    background: black;
    color: white;
    box-shadow: 0 0 25px red;
    animation: pulse 1.5s infinite alternate;
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

    st.markdown(f'<div class="main-header floating-animation">⚽🔥 {TOURNAMENT_NAME} 🔥⚽</div>', unsafe_allow_html=True)
    
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
    #st.markdown('<div class="tournament-container">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("📊 League Table")
        
        teams_df = get_teams()
        
        if not teams_df.empty:
            for i, (_, team) in enumerate(teams_df.iterrows(), 1):
                gd = team['goals_for'] - team['goals_against']
                
                if i <= 4:
                    position_class = f"position-{i}"
                else:
                    position_class = "position-other"
                #  pulse-animation">
                st.markdown(f'''
                <div class="scoreboard-tile">
                    <div style="display: flex; align-items: center; justify-content: space-between;">
                        <div style="display: flex; align-items: center;">
                            <span class="team-position {position_class}">{i}</span>
                            <span style="font-size: 1.3rem; font-weight: 600;color: #000000;">{team['name']}</span>
                        </div>
                        <div style="display: flex; gap: 2rem; align-items: center;">
                            <div style="text-align: center;">
                                <div style="font-size: 0.9rem; color: #666;">Played</div>
                                <div style="font-size: 1.2rem; font-weight: 600;color: #000000;">{team['matches_played']}</div>
                            </div>
                            <div style="text-align: center;">
                                <div style="font-size: 0.9rem; color: #666;">GD</div>
                                <div style="font-size: 1.2rem; font-weight: 600; color: {'green' if gd > 0 else 'red' if gd < 0 else 'orange'};">{gd:+d}</div>
                            </div>
                            <div style="text-align: center;">
                                <div style="font-size: 0.9rem; color: #666;">Points</div>
                                <div style="font-size: 1.4rem; font-weight: 700; color: #1B5E20;">{team['points']}</div>
                            </div>
                        </div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
        else:
            st.info("No teams available. Please upload fixtures first.")
    
    with col2:
        st.subheader("📈 Tournament Stats")
        
        matches_df = get_matches()
        total_matches = len(matches_df)
        completed_matches = len(matches_df[matches_df['completed'] == True])
        
        st.markdown(f'''
        <div class="stats-card">
            <h3 style="color: #000000;">📊 Match Statistics</h3>
            <p style="color: #000000;"><strong>Total Matches:</strong> {total_matches}</p>
            <p style="color: #000000;"><strong>Completed:</strong> {completed_matches}</p>
            <p style="color: #000000;"><strong>Remaining:</strong> {total_matches - completed_matches}</p>
        </div>
        ''', unsafe_allow_html=True)
        
        if not teams_df.empty:
            top_team = teams_df.iloc[0]
            st.markdown(f'''
            <div class="stats-card">
                <h3 style="color: #000000;">🏆 Current Leader</h3>
                <p style="color: #000000;"><strong>{top_team['name']}</strong></p>
                <p style="color: #000000;">Points: {top_team['points']}</p>
                <p style="color: #000000;">Goals: {top_team['goals_for']}</p>
                <p style="color: #000000;">GD: {top_team['goals_for'] - top_team['goals_against']:+d}</p>
            </div>
            ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_fixtures():
    #st.markdown('<div class="tournament-container">', unsafe_allow_html=True)
    st.subheader("📅 Match Fixtures")
    
    matches_df = get_matches()
    
    if matches_df.empty:
        st.warning("No fixtures available. Please upload an Excel file with fixtures.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    if st.session_state.admin_logged_in:
        #st.markdown('<div class="admin-panel">', unsafe_allow_html=True)
        st.info("🔧 Admin Mode: Update match scores")
        st.markdown('</div>', unsafe_allow_html=True)
        
        for _, match in matches_df.iterrows():
            status = "✅ Completed" if match['completed'] else "⏳ Pending"
            fixture_class = "match-completed" if match['completed'] else "match-pending"
            
            with st.expander(f"{match['match_name']}: {match['team1']} vs {match['team2']} - {status}", 
                           expanded=not match['completed']):
                
                col1, col2, col3 = st.columns([2, 1, 2])
                
                with col1:
                    st.markdown(f"**🏠 {match['team1']}**")
                    score1 = st.number_input("Goals", 
                                           min_value=0, max_value=20, 
                                           value=int(match['score1']) if match['completed'] else 0,
                                           key=f"score1_{match['id']}")
                
                with col2:
                    st.markdown("**VS**")
                    if st.button("Update", key=f"update_{match['id']}", type="primary"):
                        score2 = st.session_state[f"score2_{match['id']}"]
                        if update_match_score(match['id'], score1, score2):
                            st.success("Updated!")
                            st.rerun()
                
                with col3:
                    st.markdown(f"**🚌 {match['team2']}**")
                    score2 = st.number_input("Goals", 
                                           min_value=0, max_value=20, 
                                           value=int(match['score2']) if match['completed'] else 0,
                                           key=f"score2_{match['id']}")
                
                if match['completed']:
                    winner = match['team1'] if match['score1'] > match['score2'] else match['team2'] if match['score2'] > match['score1'] else "Draw"
                    st.success(f"🏆 Final Score: {match['team1']} {int(match['score1'])} - {int(match['score2'])} {match['team2']} ({winner})")
    else:
        # Read-only view
        completed_matches = matches_df[matches_df['completed'] == True]
        pending_matches = matches_df[matches_df['completed'] == False]
        
        if not completed_matches.empty:
            st.subheader("✅ Completed Matches")
            for _, match in completed_matches.iterrows():
                result_emoji = "🏆" if match['score1'] != match['score2'] else "🤝"
                st.markdown(f'''
                <div class="match-fixture match-completed">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="font-weight: 600; font-size: 1.1rem; color: #000000;">{match['match_name']}</div>
                        <div style="text-align: center; font-size: 1.3rem; font-weight: 700; color: #000000;">
                            {match['team1']} <span style="color: #1B5E20;">{int(match['score1'])} - {int(match['score2'])}</span> {match['team2']}
                        </div>
                        <div style="font-size: 1.5rem;">{result_emoji}</div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
        
        if not pending_matches.empty:
            st.subheader("⏳ Upcoming Matches")
            for _, match in pending_matches.iterrows():
                st.markdown(f'''
                <div class="match-fixture match-pending">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="font-weight: 600; font-size: 1.1rem; color: #000000;">{match['match_name']}</div>
                        <div style="text-align: center; font-size: 1.3rem; font-weight: 700; color: #000000;">
                            {match['team1']} <span style="color: #FF9800;">vs</span> {match['team2']}
                        </div>
                        <div style="font-size: 1.5rem;">⏳</div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)


# Complete the missing show_knockout_bracket function
def show_knockout_bracket():
    #st.markdown('<div class="bracket-container">', unsafe_allow_html=True)
    st.subheader("🎯 Knockout Bracket")
    
    # Check if league stage is complete enough for knockout
    matches_df = get_matches()
    if matches_df.empty or len(matches_df[matches_df['completed'] == True]) < len(matches_df) * 0.8:
        st.warning("⚠️ Complete more league matches to generate knockout bracket")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    # Generate bracket if admin
    if st.session_state.admin_logged_in:
        if st.button("🔄 Generate Knockout Bracket", type="primary"):
            generate_knockout_bracket()
            st.success("Knockout bracket generated!")
            st.rerun()
    
    knockout_df = get_knockout_matches()
    
    if knockout_df.empty:
        st.info("No knockout matches generated yet. Use the button above to create bracket.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    # Display bracket visually
    col1, col2, col3 = st.columns([2, 1, 2])
    
    # Semi-finals
    semis = knockout_df[knockout_df['stage'] == 'semi']
    with col1:
        st.markdown("### Semi-Finals")
        for _, match in semis.iterrows():
            status = "✅" if match['completed'] else "⏳"
            score_display = f"{int(match['score1'])} - {int(match['score2'])}" if match['completed'] else "vs"
            
            st.markdown(f'''
            <div class="bracket-match bracket-semi floating-animation">
                <div style="font-weight: 700; margin-bottom: 1rem;color: #000000;">{match['match_name']}</div>
                <div style="font-size: 1.2rem;color: #000000;">{match['team1']} {score_display} {match['team2']}</div>
                <div style="margin-top: 1rem; font-size: 1.5rem;color: #000000;">{status}</div>
            </div>
            ''', unsafe_allow_html=True)
            
            # Admin score update
            if st.session_state.admin_logged_in and not match['completed']:
                with st.expander(f"Update {match['match_name']}"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        s1 = st.number_input(f"{match['team1']} Goals", 0, 20, key=f"ko_s1_{match['id']}")
                    with col_b:
                        s2 = st.number_input(f"{match['team2']} Goals", 0, 20, key=f"ko_s2_{match['id']}")
                    
                    if st.button("Update Score", key=f"ko_update_{match['id']}"):
                        update_knockout_match_score(match['id'], s1, s2)
                        st.success("Score updated!")
                        st.rerun()
    
    # Connection lines (visual)
    with col2:
        st.markdown("### 🏆")
        st.markdown('''
        <div style="height: 200px; display: flex; align-items: center; justify-content: center;">
            <div style="font-size: 3rem;color: #000000; animation: pulse 2s infinite;">⚽</div>
        </div>
        ''', unsafe_allow_html=True)
    
    # Final
    with col3:
        st.markdown("### Final")
        final = knockout_df[knockout_df['stage'] == 'final']
        if not final.empty:
            final_match = final.iloc[0]
            status = "🏆" if final_match['completed'] else "⏳"
            
            if final_match['team1'] == 'TBD':
                display_text = "Awaiting Semi-Final Results"
                teams_display = "TBD vs TBD"
            else:
                score_display = f"{int(final_match['score1'])} - {int(final_match['score2'])}" if final_match['completed'] else "vs"
                teams_display = f"{final_match['team1']} {score_display} {final_match['team2']}"
                display_text = final_match['match_name']
            
            st.markdown(f'''
            <div class="bracket-match bracket-final pulse-animation">
                <div style="font-weight: 800; margin-bottom: 1rem;color: #000000;">{display_text}</div>
                <div style="font-size: 1.3rem;">{teams_display}</div>
                <div style="margin-top: 1rem; font-size: 2rem;color: #000000;">{status}</div>
            </div>
            ''', unsafe_allow_html=True)
            
            # Admin final score update
            if st.session_state.admin_logged_in and not final_match['completed'] and final_match['team1'] != 'TBD':
                with st.expander("Update Final"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        f1 = st.number_input(f"{final_match['team1']} Goals", 0, 20, key=f"final_s1_{final_match['id']}")
                    with col_b:
                        f2 = st.number_input(f"{final_match['team2']} Goals", 0, 20, key=f"final_s2_{final_match['id']}")
                    
                    if st.button("Update Final Score", key=f"final_update_{final_match['id']}",type="primary"):
                        update_knockout_match_score(final_match['id'], f1, f2)
                        st.success("Final score updated!")
                        time.sleep(1)  # Allow time for update to process
                        st.rerun()
                    else:
                        st.error("Failed to update the final score. Please try again.")
    
    # Tournament winner display
    if not final.empty and final.iloc[0]['completed']:
        final_match = final.iloc[0]
        winner = final_match['team1'] if final_match['score1'] > final_match['score2'] else final_match['team2']
        st.markdown(f'''
        <div style="text-align: center; margin-top: 3rem;">
            <div style="background: linear-gradient(135deg, #FFD700 0%, #FFA000 100%); 
                        padding: 2rem; border-radius: 20px; border: 3px solid #FF8F00;">
                <h1 style="color: #1B5E20; font-size: 2.5rem; margin: 0;">🏆 TOURNAMENT CHAMPION 🏆</h1>
                <h2 style="color: #1B5E20; font-size: 2rem; margin: 1rem 0;">{winner}</h2>
            </div>
        </div>
        ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

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