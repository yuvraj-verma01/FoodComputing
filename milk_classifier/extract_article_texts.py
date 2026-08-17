import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import numpy as np

import cloudscraper

def extract_text(url):
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        response = scraper.get(url, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Try to extract text from <p> tags first as it usually contains the article body
        paragraphs = soup.find_all('p')
        text = '\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
        
        # Fallback to whole body text if no paragraphs are found
        if not text:
            text = soup.get_text(separator='\n', strip=True)
            
        return text, 1.0, None
    except Exception as e:
        return None, 0.0, str(e)

def main():
    file_path = "milk_adulteration_articles_master.xlsx"
    print(f"Loading {file_path}...")
    
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        return

    # To be efficient, we only scrape if the text is missing or previous scrape was unsuccessful
    needs_scraping = df['text'].isna() | (df['text'] == '') | (df['scrape_success'] != 1.0)
    
    target_indices = df[needs_scraping].index
    print(f"Found {len(target_indices)} articles that need text extraction.")
    
    # Track if we made any changes to save time if nothing was scraped
    changes_made = False
    
    for i, idx in enumerate(target_indices):
        url = df.loc[idx, 'url']
        if pd.isna(url) or not isinstance(url, str) or not url.startswith('http'):
            print(f"[{i+1}/{len(target_indices)}] Skipping invalid URL: {url}")
            continue
            
        print(f"[{i+1}/{len(target_indices)}] Scraping: {url}")
        
        text, success, error = extract_text(url)
        
        if success == 1.0:
            df.loc[idx, 'text'] = text
            df.loc[idx, 'scrape_success'] = 1.0
            df.loc[idx, 'error'] = np.nan
            print("  -> Success")
        else:
            df.loc[idx, 'scrape_success'] = 0.0
            df.loc[idx, 'error'] = error
            print(f"  -> Failed: {error}")
            
        changes_made = True
        time.sleep(1.5) # Polite delay between requests
        
    if changes_made:
        print(f"\nSaving updated data back to {file_path}...")
        try:
            df.to_excel(file_path, index=False)
            print("Done!")
        except Exception as e:
            print(f"Error saving to Excel. Is the file open in another program? Error: {e}")
    else:
        print("No articles needed scraping. No changes made.")

if __name__ == "__main__":
    main()
