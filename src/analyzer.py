import pandas as pd
import re
import os

DETAILS_FILE = "data/game_details.csv"
STANDINGS_FILE = "data/standings.csv"

def generate_standings(df):
    """
    Data Transformation Logic:
    1. Filters for 'Final' period scores to determine W/L/T.
    2. Processes games chronologically to accurately calculate Win/Loss Streaks.
    3. Implements the official DMHL tie-breaker system (Pts > Wins > Diff > GF).
    """
    # Isolate game results and sort by ID for chronological accuracy
    finals = df[(df['EventType'] == 'PeriodScore') & (df['Period'] == 'Final')].sort_values('GameID')
    std, hist = {}, {}

    # Iterate through games to build team summaries
    for gid, gdata in finals.groupby('GameID'):
        tms = gdata['Team'].unique()
        if len(tms) != 2: continue # Ensure we have two teams (ignores forfeits/bye weeks)
        
        t1, t2 = tms[0], tms[1]
        try:
            # Convert text scores to integers for mathematical comparison
            s1, s2 = int(gdata[gdata['Team']==t1].iloc[0]['Description']), int(gdata[gdata['Team']==t2].iloc[0]['Description'])
        except: continue

        # Initialize team dicts if they haven't been seen yet
        for t in [t1, t2]:
            if t not in std:
                std[t] = {'GP': 0, 'W': 0, 'L': 0, 'T': 0, 'Pts': 0, 'RW': 0, 'GF': 0, 'GA': 0, 'PIM': 0}
                hist[t] = [] # List to track the result of every game in order

        # Update core game stats
        std[t1]['GP'] += 1; std[t2]['GP'] += 1
        std[t1]['GF'] += s1; std[t1]['GA'] += s2
        std[t2]['GF'] += s2; std[t2]['GA'] += s1

        # Point allocation and History tracking
        if s1 > s2:
            std[t1]['W'] += 1; std[t1]['Pts'] += 2; std[t1]['RW'] += 1; std[t2]['L'] += 1
            hist[t1].append('W'); hist[t2].append('L')
        elif s2 > s1:
            std[t2]['W'] += 1; std[t2]['Pts'] += 2; std[t2]['RW'] += 1; std[t1]['L'] += 1
            hist[t1].append('L'); hist[t2].append('W')
        else:
            std[t1]['T'] += 1; std[t1]['Pts'] += 1; std[t2]['T'] += 1; std[t2]['Pts'] += 1
            hist[t1].append('T'); hist[t2].append('T')

    # Data Post-Processing: Convert the nested dictionary into a structured DataFrame
    res = pd.DataFrame.from_dict(std, orient='index').reset_index().rename(columns={'index': 'Team'})
    
    # Calculate Goal Differential (The 'Diff' column)
    res['Diff'] = res['GF'] - res['GA']
    
    # Calculate Last 10 games using List Slicing: history[-10:] grabs the tail of the list
    res['L10'] = res['Team'].apply(lambda x: f"{hist[x][-10:].count('W')}-{hist[x][-10:].count('L')}-{hist[x][-10:].count('T')}")
    
    def get_streak(h):
        """Walks backwards from the latest game to count the current streak length."""
        if not h: return "-"
        rev = h[::-1] # Reverse the list
        curr = rev[0] # Most recent result
        count = 0
        for r in rev:
            if r == curr: count += 1
            else: break
        return f"{curr}{count}"
    
    res['Streak'] = res['Team'].apply(lambda x: get_streak(hist[x]))

    # Multi-tier Sorting: Logic handles the league's specific tie-breaker priorities
    res = res.sort_values(['Pts', 'W', 'Diff', 'GF'], ascending=False).reset_index(drop=True)
    
    # Final Rank assignment based on sorted position
    res.insert(0, 'Rank', res.index + 1)
    return res

def main():
    """
    Controller: Reads the scraped detail file, executes analytics, 
    and saves the structured standings to a new CSV.
    """
    if not os.path.exists(DETAILS_FILE): 
        print("No data found. Run the scraper first.")
        return
        
    df = pd.read_csv(DETAILS_FILE)
    standings = generate_standings(df)
    
    # Outputting the calculated standings as a tidy CSV for the App to consume
    standings.to_csv(STANDINGS_FILE, index=False)
    
    # Console Display Settings: ensures the table doesn't 'wrap' and stays readable
    pd.set_option('display.max_columns', None); pd.set_option('display.width', 1000)
    print("🏆 STANDINGS UPDATED\n", standings.to_string(index=False))

if __name__ == "__main__": main()