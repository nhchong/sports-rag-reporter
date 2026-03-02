import os
import re
from google import genai
from dotenv import load_dotenv

# Initialize environment variables
load_dotenv()

def evaluate_dispatch_bias(filepath):
    """
    Acts as the Executive Editor for 'The Low B Dispatch'.
    Ensures the 'Senior Columnist' persona remains objective and fair
    without stripping away the analytical wit and community flair.
    """
    
    # 1. API CONFIGURATION
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ Error: No API Key found in .env.")
        return False
        
    client = genai.Client(api_key=api_key)

    print(f"🔍 Auditing Narrative Balance: {filepath}")
    
    # 2. FILE INGESTION
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            article_text = f.read()
    except FileNotFoundError:
        print(f"❌ File not found: {filepath}")
        return False

    # 3. THE BRAND-AWARE BIAS FRAMEWORK
    # This framework distinguishes between 'Journalistic Color' and 'Unfair Bias'.
    prompt = f"""
    You are an Auditor for a sophisticated, data-driven sports newsletter. 
    Evaluate the text below for 'Narrative Bias' while respecting the 'The Athletic' style guide.

    --- AUDIT CRITERIA ---
    1. ANALYTICAL COLOR (ALLOW): High-energy verbs and metaphors (e.g., 'dominance', 'relentless', 'chippy') 
       are NOT bias if they align with the statistical reality of the game.
    2. SUBJECTIVE SKEW (FLAG): Do not allow the narrative to favor one team's "spirit" or "effort" 
       while dismissing the opponent's performance.
    3. DATA-DRIVEN FAIRNESS (REQUIRED): All teams must be mentioned. Losing teams' star players 
       must receive objective credit for their statistical output.
    4. NO CHARACTER ATTACKS: Avoid demeaning adjectives (e.g., 'lazy', 'pathetic', 'undeserving').
    ----------------------

    Text to Audit: {article_text}
    
    Categories to evaluate:
    1. Narrative Imbalance: Does the report focus disproportionately on one team's "heroics" while ignoring the opponent's data?
    2. Subjective Dismissal: Use of demeaning language toward a team (e.g., calling them 'flat' or 'outclassed' without context).
    3. Framing Bias: Presenting a win as "destiny" or a loss as "inevitable" rather than a result of play.
    4. Selective Representation: Omitting key statistical performers from the losing side to fit a specific "story."
    5. Overall Objectivity: Is the tone that of an impartial peer (Pass) or a biased fan/homer (Fail)?

    Format your response STRICTLY as follows:
    - [Category Name]: [Present/Absent]
    (ONLY if Present, add a new line starting with '>') [Specific snippet and how it creates unfair bias]

    Do not provide snippets for 'Absent' categories.
    """

    try:
        # 4. INFERENCE ENGINE
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite", 
            contents=prompt
        )
        evaluation = response.text.strip()
    except Exception as e:
        print(f"❌ AI Generation Error: {e}")
        return False

    # 5. PRETTY PRINT / UI LOGIC
    print("\n" + "="*50)
    print("🛡️  THE LOW B DISPATCH: BIAS & INTEGRITY AUDIT")
    print("="*50)

    YELLOW, GREEN, RED, BOLD, ENDC = '\033[93m', '\033[92m', '\033[91m', '\033[1m', '\033[0m'

    lines = evaluation.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue

        if re.search(r':\s*Present', line, re.IGNORECASE) or re.search(r':\s*Fail', line, re.IGNORECASE):
            print(f"{YELLOW}{BOLD}⚠️ {line}{ENDC}")
        elif re.search(r':\s*Absent', line, re.IGNORECASE) or re.search(r':\s*Pass', line, re.IGNORECASE):
            print(f"{GREEN}✅ {line}{ENDC}")
        elif line.startswith(">"):
            print(f"   {line}")
        else:
            print(f"   {line}")

    # 6. GATEKEEPING LOGIC
    # Allows for 1 minor flag (warning), but halts for 2+ (systemic bias).
    present_count = len(re.findall(r'\bPresent\b', evaluation, re.IGNORECASE))
    
    print("-" * 50)
    if present_count >= 2:
        print(f"{RED}{BOLD}🛑 AUDIT FAILED: Systemic bias detected. Human-in-the-loop review required.{ENDC}")
        return False
    elif present_count == 1:
        print(f"{YELLOW}{BOLD}⚠️  MINOR SKEW DETECTED: Review the flag above. Proceeding with publication.{ENDC}")
        return True
    
    print(f"{GREEN}{BOLD}🎉 AUDIT PASSED: Content is objective and balanced.{ENDC}")
    return True

if __name__ == "__main__":
    POSTS_DIR = "docs/_posts"
    if os.path.exists(POSTS_DIR):
        all_files = [os.path.join(POSTS_DIR, f) for f in os.listdir(POSTS_DIR) if f.endswith(".md")]
        if all_files:
            all_files.sort(key=os.path.getmtime, reverse=True)
            evaluate_dispatch_bias(all_files[0])
        else:
            print("❌ No posts found.")
    else:
        print(f"❌ Directory not found: {POSTS_DIR}")