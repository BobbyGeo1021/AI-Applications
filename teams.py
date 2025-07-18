# Script to create sample teams.xlsx file
import pandas as pd
import os

# Create assets directory if it doesn't exist
os.makedirs('assets', exist_ok=True)

# Sample team data
teams_data = {
    'Team Name': [
        'DFC',
        'The Gregorians [Chinchwad]',
        'The Gregorians [Dighi]',
        'STFU Khadki A',
        'STFU Khadki B',
        'STFU Khadki C',
        'STFU Khadki D',
        'Ghorpadi A',
        'Ghorpadi B',
        'GFU [Bhosari]'
    ]
}

# Create DataFrame and save to Excel
df = pd.DataFrame(teams_data)
df.to_excel('assets/teams.xlsx', index=False)

print("Sample teams.xlsx file created successfully!")
print("Teams included:")
for i, team in enumerate(df['Team Name'], 1):
    print(f"{i}. {team}")