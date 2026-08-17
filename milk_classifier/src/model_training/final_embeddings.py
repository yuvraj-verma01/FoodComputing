import pandas as pd
import numpy as np
from sklearn.svm import SVC
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sentence_transformers import SentenceTransformer
from .evaluate_models import compute_metrics

def train_and_evaluate_final_embeddings(full_texts, milk_texts, labels, df, output_dir, n_splits=5):
    print("Loading SentenceTransformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    print("Generating embeddings for full_texts...")
    X_full = model.encode(full_texts, show_progress_bar=True)
    
    print("Generating embeddings for milk_texts...")
    X_milk = model.encode(milk_texts, show_progress_bar=True)
    
    representations = {
        "title_plus_body_full": X_full,
        "title_plus_milk_windows": X_milk
    }
    
    results = []
    y = np.array(labels)
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    
    for repr_name, X in representations.items():
        print(f"Evaluating Embeddings on {repr_name}...")
        
        full_preds = np.zeros(len(df))
        full_probs = np.zeros(len(df))
        
        for train_idx, test_idx in cv.split(X, y):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            classifier = SVC(kernel='rbf', probability=True, class_weight='balanced', random_state=42)
            classifier.fit(X_train_scaled, y_train)
            
            full_preds[test_idx] = classifier.predict(X_test_scaled)
            full_probs[test_idx] = classifier.predict_proba(X_test_scaled)[:, 1]
            
        metrics = compute_metrics(y, full_preds, full_probs)
        
        pred_df = df.copy()
        pred_df["true_label"] = y
        pred_df["predicted_label"] = full_preds
        pred_df["probability"] = full_probs
        
        results.append({
            "model_name": "all-MiniLM-L6-v2 + RBF SVM",
            "representation": repr_name,
            "metrics": metrics,
            "predictions_df": pred_df
        })
        
    return results
