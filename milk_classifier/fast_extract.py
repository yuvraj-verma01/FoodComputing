import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import numpy as np
import cloudscraper
import re
import concurrent.futures

ILLEGAL_CHARACTERS_RE = re.compile(r'[\000-\010]|[\013-\014]|[\016-\037]')

def extract_text(url):
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        response = scraper.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        paragraphs = soup.find_all('p')
        text = '\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
        
        if not text:
            text = soup.get_text(separator='\n', strip=True)
            
        text = ILLEGAL_CHARACTERS_RE.sub(r'', text)
        return text, 1.0, None
    except Exception as e:
        return None, 0.0, str(e)

def process_row(idx, url):
    if pd.isna(url) or not isinstance(url, str) or not url.startswith('http'):
        return idx, None, 0.0, "Invalid URL"
    text, success, error = extract_text(url)
    return idx, text, success, error

def main():
    file_path = "milk_adulteration_articles_master.xlsx"
    print(f"Loading {file_path}...")
    
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        return

    needs_scraping = df['text'].isna() | (df['text'] == '') | (df['scrape_success'] != 1.0)
    target_indices = df[needs_scraping].index
    print(f"Found {len(target_indices)} articles that need text extraction.")
    
    if len(target_indices) == 0:
        print("No articles needed scraping.")
        return

    changes_made = False
    
    # We will use ThreadPoolExecutor to speed up extraction
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_row, idx, df.loc[idx, 'url']): idx for idx in target_indices}
        for future in concurrent.futures.as_completed(futures):
            idx, text, success, error = future.result()
            completed += 1
            if completed % 50 == 0:
                print(f"[{completed}/{len(target_indices)}] Processed...")
                
            if success == 1.0:
                df.loc[idx, 'text'] = text
                df.loc[idx, 'scrape_success'] = 1.0
                df.loc[idx, 'error'] = np.nan
            else:
                df.loc[idx, 'scrape_success'] = 0.0
                df.loc[idx, 'error'] = error
            changes_made = True
            
    if changes_made:
        print(f"\nSaving updated data back to {file_path}...")
        try:
            # Clean all texts just in case
            df['text'] = df['text'].apply(lambda x: ILLEGAL_CHARACTERS_RE.sub(r'', str(x)) if pd.notna(x) else x)
            df.to_excel(file_path, index=False)
            print("Done!")
        except Exception as e:
            print(f"Error saving to Excel: {e}")
            df.to_csv("milk_adulteration_articles_master_backup.csv", index=False)
            print("Saved to backup CSV instead.")

if __name__ == "__main__":
    main()
