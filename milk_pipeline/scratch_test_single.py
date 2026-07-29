import json
from pathlib import Path
import config
from pipeline import filter_relevance

def test_single():
    art = {
        "url": "https://www.siasat.com/toddy-sold-in-milk-packets-270-litres-seized-from-medchal-hotel-3247412/",
        "title": "Toddy sold in milk packets: 270 litres seized from Medchal hotel",
        "text": "",
        "publish_date": "2025-07-18"
    }
    
    score = filter_relevance.score_article(art, [], 1, config.KEYWORD_BLOCKLIST)
    print(f"Score: {score}")

if __name__ == "__main__":
    test_single()
