import json
from pathlib import Path
import sys
import os

# Import the NEW config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from pipeline import filter_relevance

def refilter():
    path = Path(r"c:\Users\Writika\milk_pipeline\data\round_5_filtered\filtered_results.json")
    if not path.exists():
        print(f"{path} does not exist!")
        return

    with open(path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    passing_clean = []
    for art in articles:
        corpus = " ".join([
            art.get("title", ""),
            art.get("text", ""),
            art.get("url", ""),
        ]).lower()
        
        blocked = False
        for bad_term in config.KEYWORD_BLOCKLIST:
            if bad_term.lower() in corpus:
                blocked = True
                print(f"Blocked: {art.get('title', '')} (due to '{bad_term}')")
                break
                
        if not blocked:
            passing_clean.append(art)

    print(f"\nRefiltered from {len(articles)} to {len(passing_clean)} articles.")
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(passing_clean, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    refilter()
