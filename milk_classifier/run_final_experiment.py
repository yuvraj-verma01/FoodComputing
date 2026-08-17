import pandas as pd
from pathlib import Path
from src.model_training.build_text_representations import build_final_representations
from src.model_training.evaluate_models import select_best_models, export_results_to_excel
from src.model_training.final_tfidf import train_and_evaluate_final_tfidf
from src.model_training.final_embeddings import train_and_evaluate_final_embeddings
from src.model_training.final_transformers import train_and_evaluate_final_transformers

def load_milk_dataset(excel_path: str) -> pd.DataFrame:
    """Loads master excel dataset, filtering for valid scraped texts and labels."""
    xls = pd.ExcelFile(excel_path)
    df = pd.read_excel(xls, sheet_name="All Articles")
    
    # Filter for successfully scraped articles with valid body text
    # Assuming scrape_success might not exist, checking text explicitly
    if "scrape_success" in df.columns:
        df = df[(df["scrape_success"] == 1.0) & (df["text"].notna()) & (df["text"].astype(str).str.strip() != "")]
    else:
        df = df[(df["text"].notna()) & (df["text"].astype(str).str.strip() != "")]
        
    # Column mapping
    df["article_text"] = df["text"].astype(str).str.strip()
    df["title"] = df["title"].fillna("").astype(str).str.strip() if "title" in df.columns else ""
    df["label"] = df["relevance"].astype(int)
    
    print(f"Loaded {len(df)} valid articles from {excel_path}")
    print(f"Class Balance -> Relevant (1): {(df['label'] == 1).sum()}, Irrelevant (0): {(df['label'] == 0).sum()}")
    return df.reset_index(drop=True)

def main():
    output_dir = Path("reports/milk_model_training")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Load Data
    print("\n--- Loading Data ---")
    df = load_milk_dataset("milk_adulteration_articles_master.xlsx")
    labels = df["label"].values
    
    # 2. Build Milk-Specific Text Representations
    print("\n--- Building Text Representations ---")
    reps = build_final_representations(df)
    full_texts = reps["title_plus_body_full"]
    milk_texts = reps["title_plus_milk_windows"]
    
    results = []
    
    # 3. Train Models
    print("\n--- Training TF-IDF Models ---")
    results += train_and_evaluate_final_tfidf(reps, labels, df, output_dir, n_splits=5)
    
    print("\n--- Training Embedding Models ---")
    results += train_and_evaluate_final_embeddings(full_texts, milk_texts, labels, df, output_dir, n_splits=5)
    
    print("\n--- Training Transformer Models ---")
    results += train_and_evaluate_final_transformers(reps, labels, df, output_dir, n_splits=5)
    
    # 4. Find Best Model and Export Metrics to Excel
    print("\n--- Exporting Results ---")
    if results:
        best_f1, best_recall = select_best_models(results)
        excel_file = output_dir / "Milk_Adulteration_Model_Results.xlsx"
        export_results_to_excel(results, best_f1_result=best_f1, excel_path=str(excel_file))
        print("Done!")
    else:
        print("No results to export.")

if __name__ == "__main__":
    main()
