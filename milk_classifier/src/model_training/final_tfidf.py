import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold
from .evaluate_models import compute_metrics

def get_tfidf_pipeline():
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.9
    )
    # Using LinearSVC with CalibratedClassifierCV to get probabilities
    svm = LinearSVC(class_weight='balanced', random_state=42, max_iter=10000)
    classifier = CalibratedClassifierCV(svm, cv=5)
    
    return Pipeline([
        ('vectorizer', vectorizer),
        ('classifier', classifier)
    ])

def train_and_evaluate_final_tfidf(reps, labels, df, output_dir, n_splits=5):
    results = []
    
    for repr_name, texts in reps.items():
        print(f"Evaluating TF-IDF on {repr_name}...")
        
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        pipeline = get_tfidf_pipeline()
        
        X = np.array(texts)
        y = np.array(labels)
        
        full_preds = np.zeros(len(df))
        full_probs = np.zeros(len(df))
        
        for train_idx, test_idx in cv.split(X, y):
            X_train, X_test = X[train_idx], X[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            
            pipeline.fit(X_train, y_train)
            
            full_preds[test_idx] = pipeline.predict(X_test)
            full_probs[test_idx] = pipeline.predict_proba(X_test)[:, 1]
            
        metrics = compute_metrics(y, full_preds, full_probs)
        
        pred_df = df.copy()
        pred_df["true_label"] = y
        pred_df["predicted_label"] = full_preds
        pred_df["probability"] = full_probs
            
        results.append({
            "model_name": "TF-IDF + Calibrated LinearSVC",
            "representation": repr_name,
            "metrics": metrics,
            "predictions_df": pred_df
        })
        
    return results
