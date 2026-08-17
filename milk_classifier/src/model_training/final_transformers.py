import pandas as pd
import numpy as np
import torch
import shutil
from sklearn.model_selection import StratifiedKFold
from transformers import AutoTokenizer, AutoModelForSequenceClassification, Trainer, TrainingArguments
from datasets import Dataset
from .evaluate_models import compute_metrics

def train_and_evaluate_final_transformers(reps, labels, df, output_dir, n_splits=5):
    # This can take a very long time, so we just run on title_plus_milk_windows
    repr_name = "title_plus_milk_windows"
    if repr_name not in reps:
        print(f"Skipping transformers, representation '{repr_name}' not found.")
        return []
        
    texts = reps[repr_name]
    y = np.array(labels)
    
    print(f"Evaluating Transformer (RoBERTa) on {repr_name}...")
    
    model_name = "roberta-base"
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_name)
    except Exception as e:
        print(f"Could not load tokenizer: {e}")
        return []
    
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    full_preds = np.zeros(len(df))
    full_probs = np.zeros(len(df))
    
    results = []
    fold = 1
    
    for train_idx, test_idx in cv.split(texts, y):
        print(f"Fold {fold}/{n_splits}")
        X_train = [texts[i] for i in train_idx]
        y_train = y[train_idx]
        X_test = [texts[i] for i in test_idx]
        y_test = y[test_idx]
        
        train_dataset = Dataset.from_dict({
            'text': X_train,
            'label': y_train
        })
        test_dataset = Dataset.from_dict({
            'text': X_test,
            'label': y_test
        })
        
        def tokenize_function(examples):
            return tokenizer(examples["text"], padding="max_length", truncation=True, max_length=512)
            
        tokenized_train = train_dataset.map(tokenize_function, batched=True)
        tokenized_test = test_dataset.map(tokenize_function, batched=True)
        
        model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)
        
        training_args = TrainingArguments(
            output_dir=f"./results_fold_{fold}",
            learning_rate=2e-5,
            per_device_train_batch_size=8,
            per_device_eval_batch_size=8,
            num_train_epochs=3,
            weight_decay=0.01,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            logging_dir='./logs',
        )
        
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_train,
            eval_dataset=tokenized_test,
        )
        
        trainer.train()
        
        predictions = trainer.predict(tokenized_test)
        preds = np.argmax(predictions.predictions, axis=-1)
        probs = torch.nn.functional.softmax(torch.tensor(predictions.predictions), dim=-1)[:, 1].numpy()
        
        full_preds[test_idx] = preds
        full_probs[test_idx] = probs
        
        shutil.rmtree(f"./results_fold_{fold}", ignore_errors=True)
        fold += 1
        
    metrics = compute_metrics(y, full_preds, full_probs)
    
    pred_df = df.copy()
    pred_df["true_label"] = y
    pred_df["predicted_label"] = full_preds
    pred_df["probability"] = full_probs
    
    results.append({
        "model_name": "RoBERTa-base",
        "representation": repr_name,
        "metrics": metrics,
        "predictions_df": pred_df
    })
    
    return results
