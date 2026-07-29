import json
import logging
from pathlib import Path

# Add project root to path so we can import pipeline
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import dedup
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("milk_pipeline")

def compile_all_raw():
    data_dir = config.DATA_DIR
    all_raw_articles = []
    
    # Find all raw_results.json files across all rounds
    raw_files = list(data_dir.glob("round_*_raw/raw_results.json"))
    
    if not raw_files:
        logger.warning("No raw_results.json files found in the data directory.")
        return
        
    logger.info(f"Found {len(raw_files)} raw result files.")
    
    # Read and aggregate all articles
    for file_path in raw_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                articles = json.load(f)
                all_raw_articles.extend(articles)
                logger.info(f"Loaded {len(articles)} articles from {file_path.parent.name}")
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            
    logger.info(f"Total raw articles collected: {len(all_raw_articles)}")
    
    # Deduplicate
    deduped_articles = dedup.dedupe(all_raw_articles)
    
    # Save to final_raw_dataset.json
    output_path = data_dir / "final_raw_dataset.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(deduped_articles, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved {len(deduped_articles)} deduped raw articles to {output_path.name}")

if __name__ == "__main__":
    compile_all_raw()
