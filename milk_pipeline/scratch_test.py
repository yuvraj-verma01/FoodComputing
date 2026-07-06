import json
from pathlib import Path
import config
from pipeline import filter_relevance

def test_toddy():
    path = Path(r"c:\Users\Writika\milk_pipeline\data\round_5_filtered\filtered_results.json")
    if not path.exists():
        print("No R5 file")
        return
        
    with open(path, "r", encoding="utf-8") as f:
        articles = json.load(f)
        
    print(f"Total articles in R5: {len(articles)}")
    
    toddy_count = 0
    for art in articles:
        corpus = " ".join([
            art.get("title", ""),
            art.get("text", ""),
            art.get("url", ""),
        ]).lower()
        
        if "toddy" in corpus:
            toddy_count += 1
            print(f"Found toddy in: {art['title']}")
            
            score = filter_relevance.score_article(art, [], 1, config.KEYWORD_BLOCKLIST)
            print(f"  -> score_article() returned: {score}")

if __name__ == "__main__":
    test_toddy()
