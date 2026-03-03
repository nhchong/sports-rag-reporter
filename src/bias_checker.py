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

    --- STRICT AUDIT CRITERIA & EXCLUSION ZONES ---
    1. ANALYTICAL COLOR (DO NOT FLAG): High-energy verbs and sports metaphors (e.g., 'dominance', 'relentless', 'chippy', 'intense', 'gritty', 'commanding') are EXPECTED and ALLOWED. If a word falls under standard sports hyperbole and aligns with the score/penalties, YOU MUST NOT FLAG IT.
    2. DATA-DRIVEN FAIRNESS (REQUIRED): Both teams and their respective key performers must be represented accurately based on their statistical output, regardless of the final score.
    3. NO ASSUMED INTENT: Do not allow the narrative to invent psychological motives (e.g., 'gave up', 'wanted it more', 'malicious') to explain the data. 
    4. NO CHARACTER ATTACKS: Avoid demeaning adjectives (e.g., 'lazy', 'pathetic', 'undeserving'). Focus on the play, not the person.
    5. NO DOUBLE COUNTING: If a snippet violates one category (e.g., Unjustified Causality), do not flag that exact same concept under another category. Choose the single most accurate violation.
    ----------------------

    Text to Audit: {article_text}
    
    Categories to evaluate:
    1. Outcome Skew: Does the report erase the losing team's positive statistical contributions just to force a "hero" narrative for the winner?
    2. Player Fixation: Is there a disproportionate focus on a single player's narrative that ignores or overshadows the actual statistical leaders of the game?
    3. Unjustified Causality: Does the text invent a direct reason for the outcome (e.g., "destiny", or blaming an entire loss on one minor penalty) without statistical backing?
    4. Assumed Intent & Moral Judgment: Does the text invent psychological motives (e.g., "lost his temper", "gave up") or assign moral labels to standard hockey plays (e.g., "malicious", "dirty")? (Reminder: DO NOT flag standard competitive adjectives like "intense" or "dominant").
    5. Subjective Dismissal: Is demeaning language used toward a team or player (e.g., 'outclassed', 'flat') without accompanying statistical context?

    Format your response STRICTLY as follows:
    - [Category Name]: [Present/Absent]
    (ONLY if Present, add a new line starting with '>') [Specific snippet and how it creates unfair bias]

    Do not provide snippets for 'Absent' categories.
    """

    try:
        # 4. INFERENCE ENGINE
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
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