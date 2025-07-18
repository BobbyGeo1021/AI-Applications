import streamlit as st
import pandas as pd
import random
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.units import inch
import io
import os
from datetime import datetime
import xlsxwriter

# Configuration
class Config:
    TEAMS_EXCEL_PATH = "assets/teams.xlsx"
    TOURNAMENT_LOGO_PATH = "assets/tournament_logo.jpg"
    OUTPUT_PDF_NAME = "IGNITE_FIXTURES.pdf"
    OUTPUT_EXCEL_NAME = "IGNITE_FIXTURES.xlsx"
    TOURNAMENT_NAME = "IGNITE 2025"

class FixtureGenerator:
    def __init__(self, teams):
        self.teams = teams
        self.fixtures = []
    
    def generate_group_stage_fixtures(self):
        """Generate fixtures using predefined pattern with random team assignment"""
        if len(self.teams) != 10:
            st.error("Exactly 10 teams are required!")
            return []
        
        # Shuffle teams for randomization
        shuffled_teams = self.teams.copy()
        random.shuffle(shuffled_teams)
        
        # Predefined match pattern ensuring each team plays exactly 3 matches
        match_pattern = [
            (0, 1), (2, 3), (4, 5), (6, 7), (8, 9),  # Round 1
            (0, 2), (1, 4), (3, 8), (5, 9), (6, 2),  # Round 2 
            (7, 4), (0, 3), (1, 5), (7, 9), (6, 8)   # Round 3
        ]
        
        # Generate matches using the pattern
        self.fixtures = []
        for i, (team1_idx, team2_idx) in enumerate(match_pattern, 1):
            self.fixtures.append({
                'Match': f"Match {i}",
                'Team 1': shuffled_teams[team1_idx],
                'Team 2': shuffled_teams[team2_idx],
                'Score': ''
            })
        
        return self.fixtures

class PDFGenerator:
    def __init__(self, fixtures, logo_path=None):
        self.fixtures = fixtures
        self.logo_path = logo_path
    
    def generate_pdf(self):
        """Generate PDF with fixtures table"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.darkgreen
        )
        
        # Add logo if available
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                logo = Image(self.logo_path, width=2*inch, height=2*inch)
                logo.hAlign = 'CENTER'
                story.append(logo)
                story.append(Spacer(1, 20))
            except:
                pass  # Skip logo if there's an error
        
        # Title
        title = Paragraph(f"{Config.TOURNAMENT_NAME} - GROUP STAGE FIXTURES", title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Create table data
        table_data = [['Match', 'Team 1', 'Team 2', 'Score']]
        for fixture in self.fixtures:
            table_data.append([
                fixture['Match'],
                fixture['Team 1'],
                fixture['Team 2'],
                fixture['Score']
            ])
        
        # Create table
        table = Table(table_data, colWidths=[1.5*inch, 2*inch, 2*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
        ]))
        
        story.append(table)
        
        # Add footer
        story.append(Spacer(1, 30))
        footer_text = f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        footer = Paragraph(footer_text, styles['Normal'])
        story.append(footer)
        
        doc.build(story)
        buffer.seek(0)
        return buffer

class ExcelHandler:
    @staticmethod
    def read_teams(file_path):
        """Read teams from Excel file"""
        try:
            df = pd.read_excel(file_path)
            # Get the first column (team names)
            teams = df.iloc[:, 0].dropna().tolist()
            return teams
        except Exception as e:
            st.error(f"Error reading teams file: {e}")
            return []
    
    @staticmethod
    def generate_fixtures_excel(fixtures):
        """Generate Excel file with fixtures"""
        buffer = io.BytesIO()
        
        # Create workbook and worksheet
        workbook = xlsxwriter.Workbook(buffer)
        worksheet = workbook.add_worksheet('Fixtures')
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#006400',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        cell_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        # Write headers
        headers = ['Match', 'Team 1', 'Team 2', 'Score']
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Write fixture data
        for row, fixture in enumerate(fixtures, 1):
            worksheet.write(row, 0, fixture['Match'], cell_format)
            worksheet.write(row, 1, fixture['Team 1'], cell_format)
            worksheet.write(row, 2, fixture['Team 2'], cell_format)
            worksheet.write(row, 3, fixture['Score'], cell_format)
        
        # Set column widths
        worksheet.set_column(0, 0, 15)  # Match
        worksheet.set_column(1, 2, 20)  # Team names
        worksheet.set_column(3, 3, 15)  # Score
        
        workbook.close()
        buffer.seek(0)
        return buffer

def main():
    # Page configuration
    st.set_page_config(
        page_title="IGNITE 2025 Tournament",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Custom CSS for football theme
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(90deg, #006400, #228B22);
        color: white;
        padding: 2rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .fixture-container {
        background: linear-gradient(135deg, #f0f8f0, #e6f3e6);
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #006400;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .vs-text {
        font-size: 1.2rem;
        font-weight: bold;
        color: #006400;
        text-align: center;
        margin: 0.5rem 0;
    }
    
    .team-name {
        font-size: 1.1rem;
        font-weight: bold;
        color: #2c5530;
        text-align: center;
        padding: 0.5rem;
        background: white;
        border-radius: 5px;
        margin: 0.2rem 0;
    }
    
    .stButton > button {
        background-color: #006400;
        color: white;
        border: none;
        padding: 0.5rem 2rem;
        border-radius: 5px;
        font-weight: bold;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        background-color: #228B22;
        transform: translateY(-2px);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Main header
    st.markdown("""
    <div class="main-header">
        <h1>⚽ IGNITE 2025 TOURNAMENT</h1>
        <p>Group Stage Fixture Generator</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'fixtures' not in st.session_state:
        st.session_state.fixtures = []
    
    # Load teams
    teams = ExcelHandler.read_teams(Config.TEAMS_EXCEL_PATH)
    
    if not teams:
        st.error("⚠️ Could not load teams. Please ensure the teams Excel file exists at the configured path.")
        st.info("Expected file structure: First column should contain team names")
        return
    
    if len(teams) != 10:
        st.error(f"⚠️ Expected 10 teams, but found {len(teams)} teams in the file.")
        return
    
    # Display teams
    st.subheader("🏆 Participating Teams")
    cols = st.columns(5)
    for i, team in enumerate(teams):
        with cols[i % 5]:
            st.info(f"**{team}**")
    
    st.divider()
    
    # Generate fixtures button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🎲 Generate Random Fixtures", use_container_width=True):
            with st.spinner("Generating fixtures..."):
                generator = FixtureGenerator(teams)
                st.session_state.fixtures = generator.generate_group_stage_fixtures()
            st.success("✅ Fixtures generated successfully!")
    
    # Display fixtures
    if st.session_state.fixtures:
        st.subheader("📋 Group Stage Fixtures")
        
        # Display in a grid
        cols = st.columns(3)
        for i, fixture in enumerate(st.session_state.fixtures):
            with cols[i % 3]:
                st.markdown(f"""
                <div class="fixture-container">
                    <h4 style="text-align: center; color: #006400; margin-bottom: 1rem;">{fixture['Match']}</h4>
                    <div class="team-name">{fixture['Team 1']}</div>
                    <div class="vs-text">VS</div>
                    <div class="team-name">{fixture['Team 2']}</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.divider()
        
        # Download section
        st.subheader("📥 Download Fixtures")
        col1, col2 = st.columns(2)
        
        with col1:
            # Generate PDF
            pdf_generator = PDFGenerator(st.session_state.fixtures, Config.TOURNAMENT_LOGO_PATH)
            pdf_buffer = pdf_generator.generate_pdf()
            
            st.download_button(
                label="📄 Download PDF",
                data=pdf_buffer.getvalue(),
                file_name=Config.OUTPUT_PDF_NAME,
                mime="application/pdf",
                use_container_width=True
            )
        
        with col2:
            # Generate Excel
            excel_buffer = ExcelHandler.generate_fixtures_excel(st.session_state.fixtures)
            
            st.download_button(
                label="📊 Download Excel",
                data=excel_buffer.getvalue(),
                file_name=Config.OUTPUT_EXCEL_NAME,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 1rem;">
        <p>⚽ IGNITE 2025 Tournament Management System</p>
        <p>Group Stage: 15 matches • Each team plays 3 unique opponents</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()