"""
Editorial Integrity & Bias Auditing Module

This module serves as the final Quality Assurance (QA) gate in the publishing pipeline. 
It leverages a secondary LLM inference call to audit generated newsletters for narrative 
skew, unjustified causality, or subjective character attacks, ensuring the output maintains 
journalistic objectivity while preserving stylistic color.
"""

import os
import re
import sys
from typing import Optional
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- CONFIGURATION & CONSTANTS ---
POSTS_DIR = "docs/_posts"

class TermColors:
    """Standardized ANSI escape codes for CLI output formatting."""
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'


def evaluate_dispatch_bias(filepath: str) -> bool:
    """
    Executes a Natural Language Processing (NLP) audit on a generated artifact.
    
    Flow:
    1. Ingests the raw Markdown text.
    2. Prompts the LLM with a strict editorial framework to classify specific bias types.
    3. Parses the structured response to count violations.
    4. Halts the CI/CD pipeline if systemic bias is detected, requiring human intervention.
    
    Args:
        filepath (str): The relative or absolute path to the generated Markdown file.
        
    Returns:
        bool: True if the audit passes or is manually overridden. Exits the system if rejected.
    """
    
    # --- PHASE 1: INITIALIZATION ---
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print(f"{TermColors.RED}❌ Error: No API Key found in environment variables.{TermColors.ENDC}")
        return False
        
    client = genai.Client(api_key=api_key)

    print(f"🔍 Auditing Narrative Balance: {filepath}")
    
    # --- PHASE 2: CONTENT INGESTION ---
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            article_text = f.read()
    except FileNotFoundError:
        print(f"{TermColors.RED}❌ Error: Target file not found at {filepath}{TermColors.ENDC}")
        return False

    # --- PHASE 3: NLP FRAMEWORK DEFINITION ---
    # This prompt establishes the boundary between acceptable stylistic flair 
    # (e.g., sports hyperbole) and unacceptable journalistic bias.
    audit_prompt = f"""
    You are an Auditor for a sophisticated, data-driven sports newsletter. 
    Evaluate the text below for 'Narrative Bias' while respecting the established style guide.

    --- STRICT AUDIT CRITERIA & EXCLUSION ZONES ---
    1. ANALYTICAL COLOR (DO NOT FLAG): High-energy verbs and sports metaphors (e.g., 'dominance', 'relentless', 'chippy', 'intense', 'gritty', 'commanding') are EXPECTED and ALLOWED. If a word falls under standard sports hyperbole and aligns with the score/penalties, YOU MUST NOT FLAG IT.
    2. DATA-DRIVEN FAIRNESS (REQUIRED): Both teams and their respective key performers must be represented accurately based on their statistical output, regardless of the final score.
    3. NO ASSUMED INTENT: Do not allow the narrative to invent psychological motives (e.g., 'gave up', 'wanted it more', 'malicious') to explain the data. 
    4. NO CHARACTER ATTACKS: Avoid demeaning adjectives (e.g., 'lazy', 'pathetic', 'undeserving'). Focus on the play, not the person.
    5. NO DOUBLE COUNTING: If a snippet violates one category, do not flag that exact same concept under another category. Choose the single most accurate violation.
    ----------------------

    Text to Audit: 
    {article_text}
    
    Categories to evaluate:
    1. Outcome Skew: Does the report erase the losing team's positive statistical contributions just to force a "hero" narrative for the winner?
    2. Player Fixation: Is there a disproportionate focus on a single player's narrative that ignores or overshadows the actual statistical leaders of the game?
    3. Unjustified Causality: Does the text invent a direct reason for the outcome (e.g., "destiny", or blaming an entire loss on one minor penalty) without statistical backing?
    4. Assumed Intent & Moral Judgment: Does the text invent psychological motives (e.g., "lost his temper", "gave up") or assign moral labels to standard hockey plays (e.g., "malicious", "dirty")? 
    5. Subjective Dismissal: Is demeaning language used toward a team or player (e.g., 'outclassed', 'flat') without accompanying statistical context?

    Format your response STRICTLY as follows:
    - [Category Name]: [Present/Absent]
    (ONLY if Present, add a new line starting with '>') [Specific snippet and how it creates unfair bias]

    Do not provide snippets for 'Absent' categories.
    """

    # --- PHASE 4: INFERENCE EXECUTION ---
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=audit_prompt
        )
        evaluation = response.text.strip()
    except Exception as e:
        print(f"{TermColors.RED}❌ LLM Inference Error: {e}{TermColors.ENDC}")
        return False

    # --- PHASE 5: RESULT PARSING & CLI RENDERING ---
    print("\n" + "=" * 50)
    print(f"🛡️  THE LOW B DISPATCH: BIAS & INTEGRITY AUDIT")
    print("=" * 50)

    # Render structured output with visual indicators
    lines = evaluation.split('\n')
    for line in lines:
        line = line.strip()
        if not line: 
            continue

        if re.search(r':\s*Present', line, re.IGNORECASE) or re.search(r':\s*Fail', line, re.IGNORECASE):
            print(f"{TermColors.YELLOW}{TermColors.BOLD}⚠️ {line}{TermColors.ENDC}")
        elif re.search(r':\s*Absent', line, re.IGNORECASE) or re.search(r':\s*Pass', line, re.IGNORECASE):
            print(f"{TermColors.GREEN}✅ {line}{TermColors.ENDC}")
        elif line.startswith(">"):
            print(f"   {line}")
        else:
            print(f"   {line}")

    # --- PHASE 6: PIPELINE GATEKEEPING ---
    # Quantify violations to determine pipeline routing
    present_count = len(re.findall(r'\bPresent\b', evaluation, re.IGNORECASE))
    
    print("-" * 50)
    
    # Gatekeeping Logic: Tolerate isolated warnings, but halt execution on systemic violations.
    if present_count >= 2:
        print(f"{TermColors.RED}{TermColors.BOLD}🛑 AUDIT FAILED: Systemic bias detected.{TermColors.ENDC}")
    elif present_count == 1:
        print(f"{TermColors.YELLOW}{TermColors.BOLD}⚠️  MINOR SKEW DETECTED: Review the flag above.{TermColors.ENDC}")
    
    # Trigger Human-in-the-Loop override protocol if any bias is flagged
    if present_count >= 1:
        choice = input("\n👨‍⚖️ EDITOR-IN-CHIEF OVERRIDE: Do you want to publish this report anyway? (y/n): ").strip().lower()
        if choice in ['y', 'yes']:
            print(f"{TermColors.GREEN}✅ Override accepted. Proceeding with publication...{TermColors.ENDC}")
            return True
        else:
            print(f"{TermColors.RED}🛑 PUBLICATION ABORTED.{TermColors.ENDC}")
            sys.exit(1) # Halt bash execution sequence
    
    print(f"{TermColors.GREEN}{TermColors.BOLD}🎉 AUDIT PASSED: Content is objective and balanced.{TermColors.ENDC}")
    return True


if __name__ == "__main__":
    # Autonomously identify and evaluate the most recently generated artifact
    if os.path.exists(POSTS_DIR):
        all_files = [os.path.join(POSTS_DIR, f) for f in os.listdir(POSTS_DIR) if f.endswith(".md")]
        
        if all_files:
            # Sort files by modification time (newest first) and audit the latest
            all_files.sort(key=os.path.getmtime, reverse=True)
            evaluate_dispatch_bias(all_files[0])
        else:
            print(f"❌ No markdown posts found in {POSTS_DIR}.")
    else:
        print(f"❌ Target directory not found: {POSTS_DIR}")