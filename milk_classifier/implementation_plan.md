# Milk Adulteration Classifier Implementation Plan

This plan outlines the steps to build the end-to-end ML text classification pipeline for detecting milk adulteration from news articles, based on the provided methodology.

## User Review Required

> [!WARNING]
> Please review the proposed architecture and let me know if you would like any changes.
> Specifically, the Transformer branch (RoBERTa) requires a GPU for training. If you are running this locally without a GPU, we may want to skip or simplify the transformer branch initially to avoid excessively long training times. 

## Open Questions

> [!IMPORTANT]
> 1. Do you have a GPU available on this machine (e.g., CUDA-enabled NVIDIA GPU)? If not, training the fine-tuned RoBERTa transformer will be very slow.
> 2. The PDF mentions a few other files (`train_sentencebert_models.py`, `train_tfidf_models.py`, `utils.py`) that were in the original repository but weren't fully shown in the document. I plan to write these from scratch based on standard practices and the descriptions provided. Does that sound good?

## Proposed Changes

We will create a structured `src` directory to hold the various modules of the machine learning pipeline, along with an orchestrator script in the root directory.

### Core Data Preprocessing & Feature Engineering

#### [NEW] src/model_training/build_text_representations.py
This file will contain the logic for the "Milk-Window" strategy, extracting relevant sentences using custom lexicons (milk terms, adulteration terms) to reduce noise from general food-safety articles.

### Model Evaluation & Metrics

#### [NEW] src/model_training/evaluate_models.py
This module will handle computing classification metrics (Precision, Recall, F1, ROC-AUC, PR-AUC) specifically for the positive class (Adulterated Milk), and will export the results to a multi-sheet Excel workbook.

### Model Branches (The Ensemble)

#### [NEW] src/model_training/final_tfidf.py
Implements Branch A: Sparse TF-IDF pipeline using word unigrams/bigrams and character n-grams piped into a Calibrated LinearSVC or Logistic Regression.

#### [NEW] src/model_training/final_embeddings.py
Implements Branch B: Dense Embeddings pipeline using `sentence-transformers/all-MiniLM-L6-v2` or `BAAI/bge-large-en-v1.5` combined with an RBF SVM classifier.

#### [NEW] src/model_training/final_transformers.py
Implements Branch C: Fine-Tuned Transformer pipeline using a RoBERTa base model to capture contextual cues from the text.

### Orchestrator

#### [NEW] run_final_experiment.py
The main script that ties everything together. It will load the dataset, build the text representations, train all three model branches using 5-fold stratified cross-validation, and then export the results via the evaluation module.

## Verification Plan

### Automated Tests
- We will run `python run_final_experiment.py` after the data extraction script finishes.
- The success criteria will be the successful generation of the `reports/milk_model_training/Milk_Adulteration_Model_Results.xlsx` file with valid evaluation metrics.

### Manual Verification
- We will manually inspect the generated Excel file to review the metrics comparison, best model predictions, and false positive/false negative cases to ensure the models are learning correctly and the data pipeline is sound.
