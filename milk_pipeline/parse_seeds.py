import json
import logging
import docx
from pathlib import Path
from pipeline.scrape_fulltext import scrape

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("milk_pipeline")

def parse_and_scrape_seeds():
    doc_path = Path("milk_sample_articles.docx")
    seeds_dir = Path("seeds")
    seeds_dir.mkdir(exist_ok=True)
    out_path = seeds_dir / "seed_articles.json"

    logger.info(f"Reading docx from {doc_path}")
    doc = docx.Document(doc_path)
    urls = [p.text.strip() for p in doc.paragraphs if p.text.strip().startswith("http")]
    
    logger.info(f"Found {len(urls)} URLs. Scraping full text...")
    
    scraped_articles = scrape(urls, timeout_seconds=15)
    
    # Filter out failed scrapes if they have no text
    valid_articles = [a for a in scraped_articles if a.get("scrape_success")]
    logger.info(f"Successfully scraped {len(valid_articles)} / {len(urls)} articles.")
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(valid_articles, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved to {out_path}")

if __name__ == "__main__":
    parse_and_scrape_seeds()
