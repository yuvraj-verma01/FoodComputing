import pandas as pd

try:
    df = pd.read_excel("milk_adulteration_articles_master.xlsx")
    print("Total rows:", len(df))
    print("Rows with text populated:", df['text'].notna().sum())
    
    print("\nRelevance value counts:")
    print(df['relevance'].value_counts(dropna=False))
    
    is_not_irrelevant = (df['relevance'] != 0) & (df['relevance'] != '0')
    print(f"\nRows marked as not irrelevant (relevance != 0): {is_not_irrelevant.sum()}")
    
    needs_scraping = df['text'].isna() | (df['text'] == '') | (df['scrape_success'] != 1.0)
    target_indices = df[is_not_irrelevant & needs_scraping].index
    print(f"Rows not irrelevant AND need scraping: {len(target_indices)}")
    
except Exception as e:
    print(f"Error: {e}")
