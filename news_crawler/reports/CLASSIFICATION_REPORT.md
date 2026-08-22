# Edible-Oil-Adulteration News — Relevance Classification Report

*Generated 2026-06-29. All metrics are 5-fold stratified cross-validation (seed 42) on the same corpus; positive class = 'relevant'.*

---

## Before / After: Corpus Correction Impact

On 2026-06-29, a manual audit of all 152 "relevant" articles identified **13 mislabelled cases** (8.5% of positives):

- **12 flipped relevant → irrelevant**: oil-reuse/degradation incidents (TPC levels, spent cooking oil) or articles where oil was incidental to a general food-safety raid.
- **1 duplicate removed**: identical Cyberabad article with two different URLs.

| | Original corpus | Cleaned corpus |
|---|---|---|
| Total labelled articles | 487 | 486 |
| Relevant | 152 | 139 |
| Irrelevant | 335 | 347 |
| Positive rate | 31.2% | 28.6% |
| Models evaluated | 64 (incl. Longformer) | 61 (Longformer excluded) |
| **Best F1** | **0.795** | **0.836** |
| Best Precision | 0.753 | 0.868 |
| Best Recall | 0.842 | 0.806 |
| Best ROC-AUC | 0.925 | 0.942 |
| Best PR-AUC | 0.850 | 0.899 |

**Interpretation.** Removing mislabelled positives raised F1 by +4.1 points (+5.2%) and precision by +11.5 points. The hard-negative confusion was partly driven by the 12 flipped articles, which were oil-adjacent (reuse/TPC/general raids) and sat exactly in the boundary the model struggled with. A cleaner positive class definition — *only adulteration/contamination of edible oil, not degradation or non-oil raids* — produced a measurably sharper decision boundary. Recall dropped slightly (−3.6 pp) because the boundary tightened.

**Best model changed:** Original best was `ens_wavg[tfidf_logreg+e5-large_lr+roberta-base | 0.31, 0.37, 0.31]`; cleaned best is `ens_wavg[tfidf_linsvm+bge-large_rbfsvm+roberta-base | 0.17, 0.67, 0.17]` — bge-large RBF SVM on oil-window receives a much larger weight (0.67 vs 0.37 for e5-large), reflecting its stronger signal on the tighter positive class.

Original results preserved in `reports/model_training/` (64 models). Cleaned results in `reports/model_training_cleaned/` (61 models).

---

## 1. Objective

Build a binary text classifier that decides whether an Indian news article reports an **edible-oil adulteration / contamination / food-safety enforcement incident involving edible oil** (label = relevant), as opposed to anything else — including the hard case of food-safety raids on *non-oil* products (sweets, dairy, meat, spices) that use the *same* enforcement vocabulary.

The classifier serves two purposes: (a) screen newly discovered URLs so a human only reviews likely-relevant ones, and (b) re-screen previously dropped URLs to recover missed articles.

## 2. Dataset

- **486 labelled articles with text** (139 relevant / 347 irrelevant, 29% positive).
- Average length **375 words**, max 1868 words.
- Class imbalance handled with `class_weight='balanced'` in every classifier.
- The corpus was assembled over four discovery rounds plus a rescreen of previously-dropped URLs:

| Round | Total | Relevant |
|---|---|---|
| 0 | 10 | 9 |
| 1 | 285 | 68 |
| 2 | 22 | 17 |
| 3 | 24 | 8 |
| 4 | 162 | 43 |

**The central difficulty — hard negatives.** Many irrelevant articles are food-safety raids on dairy/sweets/meat. They contain the exact enforcement vocabulary of relevant articles (*FSSAI, seized, raid, samples failed, adulterated*), so the task is not keyword spotting — it requires distinguishing *oil-as-the-adulterated-product* from *generic enforcement*. This is what makes the problem hard and is the lens for most observations below.

## 3. Experimental setup (held constant across all models)

- **Same corpus, same 5 stratified folds, same seed (42)** — so every model's out-of-fold probabilities align per-article and are directly comparable / ensembleable.
- **Metrics:** Accuracy, Precision, Recall, F1, ROC-AUC, PR-AUC (positive class).
- **Evaluation is by cross-validation; deployable checkpoints are refit on the full dataset** (transformers saved from the final fold).

### Three text representations

| Name | What the model sees |
|---|---|
| `title_plus_body_full` | Title + the **entire** article body, no truncation. |
| `title_plus_oil_windows` | Title + first paragraph + every **oil-mentioning** sentence (±1 neighbour). A focused, signal-dense view. |
| `title_plus_keyword_windows` | Title + sentences around any oil **or** enforcement keyword (±1). |

The **oil-window** representation keys on oil terms *only* (not enforcement terms), deliberately, so it naturally drops sentences that are about enforcement of non-oil products — directly attacking the hard-negative problem. (`ghee`/`vanaspati` are excluded as positive keywords, matching the discovery NOT-block.)

## 4. Models evaluated (61 total)

| Block | Models | Count |
|---|---|---|
| 1. **Sparse TF-IDF** | word(1–2) ⊕ char(3–5) n-grams; {Logistic Regression, Linear SVM} × 3 representations | 6 |
| 2. **Full-article embeddings** | {MiniLM, MPNet, e5-large, bge-large} × {full-chunk-mean, full-chunk-max, oil-window} × {LogReg, Linear SVM, RBF SVM} | 36 |
| 3. **Fine-tuned transformers** | {DistilBERT, RoBERTa, DeBERTa-v3} × {lead-512, oil-window-512, chunk-pool-full} | 9 |
| 4. **Ensembles** | best-of-family blends, simple-average + weighted (grid 0.2–0.8) | 10 |

**Longformer-4096 was not rerun on the cleaned corpus** (`--skip-longformer`). On the original 487-article corpus it scored F1 0.640 — worst of all transformers, ~16h wall-clock on a 6GB GPU for one model — so it was dropped from the cleaned-corpus run as not worth the cost. See §6.9 below.

**Embedding full-article handling:** the whole article is split into 512-token chunks, each embedded, then mean- or max-pooled — so embeddings genuinely see the entire article. **Transformer `chunk_pool_full`:** up to 4×512 tokens → CLS vectors → mean+max pooled → classifier head. All transformer training used fp16 + gradient accumulation to fit a 6 GB GPU.

### 4.1 Historical baseline (pre-dates this framework)

Before the embeddings/transformers/ensemble framework above existed, the project's
first model was a plain TF-IDF classifier trained by the now-superseded
`src/model_training/train_tfidf_models.py` script (not part of the 61-model run,
different vectorizer/representation code, different harness). On an earlier
corpus snapshot (486 rows, 151 relevant — pre-dating the 2026-06-29 label
cleanup) its best configuration was:

| Model | Representation | F1 | Precision | Recall | ROC-AUC |
|---|---|---|---|---|---|
| `tfidf_phrase_svm` | title_plus_body | 0.700 | 0.650 | 0.788 | 0.878 |

At the time, this *was* the best model in the project. Results live in
`reports/model_training_r4_tfidf_only_20260625_102718/` (backed up at
`reports/model_training_backup_20260626_131724/`) — outside the directories this
report reads from, which is why it doesn't appear in the ranked table below. It's
included here only as a reference point: the "final" framework's own TF-IDF
(`tfidf_logreg`/`tfidf_linsvm` in §5, using a richer word+char n-gram vectorizer)
lands at essentially the same score (F1 0.685–0.701 across runs) — TF-IDF's
ceiling on this task is real and consistent across two independent
implementations. Everything past that ceiling in this report comes from
embeddings, fine-tuning, and ensembling, not from a better bag-of-words model.

## 5. Full results — all 61 models, ranked by F1

| # | Model | Repr | F1 | Prec | Rec | ROC-AUC | PR-AUC |
|---|---|---|---|---|---|---|---|
| 1 | ens_wavg[tfidf_linsvm/full+bge-large_rbfsvm/oi | ensemble:tfidf+emb+tra | 0.836 | 0.868 | 0.806 | 0.942 | 0.899 |
| 2 | ens_wavg[bge-large_rbfsvm/oilemb+roberta-base_ | ensemble:emb+transf | 0.830 | 0.833 | 0.827 | 0.943 | 0.901 |
| 3 | ens_wavg[tfidf_linsvm/full+bge-large_rbfsvm/oi | ensemble:tfidf+emb | 0.826 | 0.872 | 0.784 | 0.933 | 0.878 |
| 4 | ens_wavg[bge-large_rbfsvm/oilemb+bge-large_rbf | ensemble:oilwin+fullar | 0.825 | 0.854 | 0.799 | 0.940 | 0.892 |
| 5 | emb_bge-large_rbfsvm | oil_window_embedding | 0.823 | 0.826 | 0.820 | 0.939 | 0.892 |
| 6 | ens_avg[tfidf_linsvm/full+bge-large_rbfsvm/oil | ensemble:tfidf+emb | 0.817 | 0.870 | 0.770 | 0.930 | 0.872 |
| 7 | ens_avg[bge-large_rbfsvm/oilemb+bge-large_rbfs | ensemble:oilwin+fullar | 0.815 | 0.840 | 0.791 | 0.938 | 0.888 |
| 8 | emb_mpnet_rbfsvm | oil_window_embedding | 0.806 | 0.778 | 0.835 | 0.928 | 0.859 |
| 9 | ens_avg[bge-large_rbfsvm/oilemb+roberta-base_l | ensemble:emb+transf | 0.800 | 0.768 | 0.835 | 0.942 | 0.898 |
| 10 | emb_bge-large_rbfsvm | full_chunk_mean | 0.800 | 0.824 | 0.777 | 0.931 | 0.874 |
| 11 | ens_avg[tfidf_linsvm/full+bge-large_rbfsvm/oil | ensemble:tfidf+emb+tra | 0.796 | 0.793 | 0.799 | 0.940 | 0.893 |
| 12 | emb_bge-large_lr | full_chunk_max | 0.793 | 0.774 | 0.813 | 0.912 | 0.835 |
| 13 | emb_minilm_rbfsvm | oil_window_embedding | 0.789 | 0.748 | 0.835 | 0.921 | 0.810 |
| 14 | emb_bge-large_lr | full_chunk_mean | 0.785 | 0.747 | 0.827 | 0.911 | 0.832 |
| 15 | emb_e5-large_rbfsvm | oil_window_embedding | 0.777 | 0.764 | 0.791 | 0.926 | 0.863 |
| 16 | emb_bge-large_rbfsvm | full_chunk_max | 0.772 | 0.789 | 0.755 | 0.928 | 0.865 |
| 17 | emb_minilm_rbfsvm | full_chunk_mean | 0.764 | 0.738 | 0.791 | 0.913 | 0.819 |
| 18 | emb_bge-large_lr | oil_window_embedding | 0.762 | 0.742 | 0.784 | 0.923 | 0.862 |
| 19 | emb_mpnet_rbfsvm | full_chunk_mean | 0.760 | 0.726 | 0.799 | 0.915 | 0.835 |
| 20 | ens_wavg[tfidf_linsvm/full+roberta-base_lead_5 | ensemble:tfidf+transf | 0.758 | 0.711 | 0.813 | 0.926 | 0.865 |
| 21 | emb_e5-large_rbfsvm | full_chunk_mean | 0.755 | 0.735 | 0.777 | 0.910 | 0.841 |
| 22 | ens_avg[tfidf_linsvm/full+roberta-base_lead_51 | ensemble:tfidf+transf | 0.755 | 0.716 | 0.799 | 0.926 | 0.862 |
| 23 | emb_mpnet_rbfsvm | full_chunk_max | 0.754 | 0.727 | 0.784 | 0.910 | 0.820 |
| 24 | emb_minilm_rbfsvm | full_chunk_max | 0.750 | 0.725 | 0.777 | 0.909 | 0.803 |
| 25 | emb_e5-large_rbfsvm | full_chunk_max | 0.748 | 0.728 | 0.770 | 0.907 | 0.832 |
| 26 | emb_e5-large_lr | oil_window_embedding | 0.734 | 0.714 | 0.755 | 0.910 | 0.827 |
| 27 | emb_mpnet_lr | oil_window_embedding | 0.729 | 0.675 | 0.791 | 0.895 | 0.797 |
| 28 | hf_roberta-base_lead_512 | title_plus_body_full | 0.722 | 0.628 | 0.849 | 0.919 | 0.838 |
| 29 | hf_deberta-v3-small_lead_512 | title_plus_body_full | 0.721 | 0.609 | 0.885 | 0.911 | 0.830 |
| 30 | emb_e5-large_lr | full_chunk_max | 0.714 | 0.701 | 0.727 | 0.895 | 0.805 |
| 31 | hf_deberta-v3-small_oil_window_512 | title_plus_oil_windows | 0.707 | 0.634 | 0.799 | 0.909 | 0.797 |
| 32 | emb_mpnet_lr | full_chunk_max | 0.704 | 0.654 | 0.763 | 0.878 | 0.778 |
| 33 | emb_minilm_lr | full_chunk_max | 0.690 | 0.662 | 0.719 | 0.851 | 0.700 |
| 34 | emb_mpnet_lr | full_chunk_mean | 0.689 | 0.656 | 0.727 | 0.871 | 0.745 |
| 35 | tfidf_linsvm | title_plus_body_full | 0.685 | 0.780 | 0.612 | 0.884 | 0.779 |
| 36 | emb_e5-large_lr | full_chunk_mean | 0.678 | 0.647 | 0.712 | 0.879 | 0.768 |
| 37 | tfidf_logreg | title_plus_oil_windows | 0.677 | 0.619 | 0.748 | 0.879 | 0.772 |
| 38 | tfidf_logreg | title_plus_body_full | 0.677 | 0.605 | 0.770 | 0.877 | 0.768 |
| 39 | hf_roberta-base_chunk_pool_full | title_plus_body_full | 0.673 | 0.612 | 0.748 | 0.874 | 0.724 |
| 40 | tfidf_linsvm | title_plus_keyword_win | 0.669 | 0.761 | 0.597 | 0.880 | 0.770 |
| 41 | tfidf_linsvm | title_plus_oil_windows | 0.669 | 0.750 | 0.604 | 0.888 | 0.777 |
| 42 | emb_minilm_lr | oil_window_embedding | 0.669 | 0.636 | 0.705 | 0.861 | 0.712 |
| 43 | tfidf_logreg | title_plus_keyword_win | 0.669 | 0.600 | 0.755 | 0.871 | 0.764 |
| 44 | emb_minilm_lr | full_chunk_mean | 0.664 | 0.617 | 0.719 | 0.849 | 0.646 |
| 45 | hf_distilbert-base-uncased_lead_512 | title_plus_body_full | 0.657 | 0.548 | 0.820 | 0.868 | 0.694 |
| 46 | hf_deberta-v3-small_chunk_pool_full | title_plus_body_full | 0.632 | 0.661 | 0.604 | 0.865 | 0.735 |
| 47 | hf_roberta-base_oil_window_512 | title_plus_oil_windows | 0.629 | 0.502 | 0.842 | 0.841 | 0.683 |
| 48 | hf_distilbert-base-uncased_oil_window_512 | title_plus_oil_windows | 0.607 | 0.546 | 0.683 | 0.829 | 0.627 |
| 49 | hf_distilbert-base-uncased_chunk_pool_full | title_plus_body_full | 0.602 | 0.600 | 0.604 | 0.837 | 0.657 |
| 50 | emb_bge-large_linsvm | oil_window_embedding | 0.552 | 0.875 | 0.403 | 0.899 | 0.808 |
| 51 | emb_bge-large_linsvm | full_chunk_mean | 0.455 | 0.860 | 0.309 | 0.898 | 0.796 |
| 52 | emb_e5-large_linsvm | oil_window_embedding | 0.454 | 0.913 | 0.302 | 0.888 | 0.781 |
| 53 | emb_mpnet_linsvm | oil_window_embedding | 0.442 | 0.824 | 0.302 | 0.869 | 0.731 |
| 54 | emb_minilm_linsvm | oil_window_embedding | 0.440 | 0.808 | 0.302 | 0.859 | 0.683 |
| 55 | emb_mpnet_linsvm | full_chunk_max | 0.436 | 0.837 | 0.295 | 0.857 | 0.740 |
| 56 | emb_bge-large_linsvm | full_chunk_max | 0.418 | 0.884 | 0.273 | 0.899 | 0.804 |
| 57 | emb_mpnet_linsvm | full_chunk_mean | 0.385 | 0.814 | 0.252 | 0.855 | 0.712 |
| 58 | emb_minilm_linsvm | full_chunk_max | 0.337 | 0.879 | 0.209 | 0.838 | 0.690 |
| 59 | emb_e5-large_linsvm | full_chunk_mean | 0.335 | 0.853 | 0.209 | 0.849 | 0.709 |
| 60 | emb_e5-large_linsvm | full_chunk_max | 0.309 | 0.897 | 0.187 | 0.864 | 0.751 |
| 61 | emb_minilm_linsvm | full_chunk_mean | 0.216 | 0.643 | 0.130 | 0.825 | 0.630 |

### Best model per family

| Family | F1 | Prec | Recall | Best model |
|---|---|---|---|---|
| Ensemble | 0.836 | 0.868 | 0.806 | ens_wavg[tfidf_linsvm/full+bge-large_rbfsvm/oilemb |
| Embedding | 0.823 | 0.826 | 0.820 | emb_bge-large_rbfsvm |
| Transformer | 0.722 | 0.628 | 0.849 | hf_roberta-base_lead_512 |
| TF-IDF | 0.685 | 0.780 | 0.612 | tfidf_linsvm |

### Best overall model

**ens_wavg[tfidf_linsvm/full+bge-large_rbfsvm/oilemb+roberta-base_lead_512/full|0.17,0.67,0.17]**

- F1 **0.8358**, Precision 0.8682, Recall 0.8058, ROC-AUC 0.9424, PR-AUC 0.8991
- A weighted blend of **TF-IDF + e5-large embedding + RoBERTa** (weights 0.31 / 0.37 / 0.31).
- Operating thresholds: high-recall 0.05, balanced 0.5, high-precision 0.84.

## 5b. Methods explained

### Sparse / lexical models

- **TF-IDF** (Term Frequency × Inverse Document Frequency) turns each article into a sparse vector of weighted n-gram counts: a term is weighted up if it is frequent in an article but rare across the corpus. We combine two views with a `FeatureUnion`: **word n-grams (1–2)** capture phrases like *'mustard oil'* / *'samples failed'*, and **character n-grams (3–5)** capture sub-word spelling and morphology — robust to Indian-English spelling variants and unseen words (*adulterat-ed/-ion*, *mislabelled/mislabeled*).
- **Logistic Regression** — a linear model that outputs a calibrated probability of 'relevant'. `class_weight='balanced'` compensates for the 31% positive rate.
- **Linear SVM** — a max-margin linear classifier; we wrap it in probability calibration (Platt/sigmoid) so it can output probabilities and join ensembles.

### Embedding models (frozen encoder + small classifier)

- A **sentence embedding** model is a pretrained neural network that maps a piece of text to a fixed-length dense vector capturing *meaning* — texts with similar meaning land near each other. The encoder is **frozen** (never trained on our labels); only a small classifier on top is trained. This is why embeddings do well on a small dataset: they bring outside knowledge and don't have to learn from our ~487 rows.
- **Four encoders:** `all-MiniLM-L6-v2` (384-d, small/fast), `all-mpnet-base-v2` (768-d), `intfloat/e5-large-v2` (1024-d, needs a `"passage: "` prefix), `BAAI/bge-large-en-v1.5` (1024-d).
- **Full-article pooling:** the whole article is split into 512-token chunks, each chunk embedded, then the chunk vectors are **mean-pooled** (`full_chunk_mean`) or **max-pooled** (`full_chunk_max`) into one document vector. This lets a 512-token encoder represent an arbitrarily long article.
- **Three classifier heads** on each embedding: **Logistic Regression**, **Linear SVM**, and **RBF SVM** (a kernel SVM that can draw a *non-linear* boundary — it was consistently the best head for embeddings).

### Fine-tuned transformers

- A **transformer** reads text with self-attention and produces context-aware representations. Unlike the frozen embedders, here we **fine-tune** — update the whole network's weights — on our labels. `DistilBERT` (small), `RoBERTa-base`, and `DeBERTa-v3-small` are standard encoders with a classification head.
- These models have a hard **512-token input limit**. We tested three ways of fitting an article into that budget:
  - **`lead_512`** — title + body truncated to the first 512 tokens (the lead).
  - **`oil_window_512`** — the focused oil-window text (below), up to 512 tokens.
  - **`chunk_pool_full`** — the full article in up to 4×512-token chunks; each chunk's `[CLS]` vector is taken, then **mean+max pooled** and passed to the head (so the model sees the whole article, ≤2048 tokens).

### Longformer

- **`allenai/longformer-base-4096`** is a transformer built for long documents: sparse + global attention lets it ingest up to **4096 tokens** directly (our longest article is ~2400 tokens, so it sees essentially everything). It is the cleanest 'whole-article transformer' test.

### Ensembles

- An ensemble **averages the predicted probabilities** of several models, then thresholds the blend. Because all models share the same folds/seed, their out-of-fold probabilities align per-article, so averaging is fair. **Simple average** = equal weights; **weighted average** = weights grid-searched over {0.2…0.8} (normalised), keeping the combination with the best F1. Ensembles help when members make *different* mistakes — here, embeddings (precise) + RoBERTa (high recall) are complementary.

## 5c. Text representations & keyword windows in detail

All three representations are built per article from its title and body.

**`title_plus_body_full`** — the title followed by the complete body, untruncated. Used directly by TF-IDF, and chunked for the embedding/transformer full-article modes.

**`title_plus_oil_windows`** (the 'oil-window') — built as:

1. Split the body into sentences.
2. **Always keep the first paragraph** (text before the first blank line, else the first two sentences) — Indian news states the key fact in the lead.
3. **Scan every sentence**; if it mentions an **oil term** (the oil lexicon below, plus the bare word *oil*), keep that sentence **plus one sentence on each side** for context.
4. Concatenate title + first paragraph + the kept oil-sentences, de-duplicated.

The key design choice: it keys on **oil terms only**, *not* enforcement terms. Sentences about enforcement of *non-oil* products (a paneer raid, a sweets seizure) contain no oil term, so they are dropped — directly removing the hard-negative vocabulary. This is the representation behind the best single model.

**`title_plus_keyword_windows`** — the same windowing idea but the trigger is **any oil *or* adulteration/enforcement keyword** (both lexicons below). It is broader, so it re-admits some of the shared enforcement vocabulary, which is why it slightly underperforms the oil-window.

Word boundaries are enforced, so *oil* matches as a whole word only — it does **not** fire inside *boil*, *spoil*, *turmoil*, or *oilseed*.

## 5d. What 'oil-relevant' means (the labelling definition)

An article is **relevant** if it documents an incident in which **edible oil itself is the adulterated / contaminated / substandard / seized / failed product**. It is **not** relevant if:

- oil is the **adulterant** used to debase *another* food (e.g. argemone oil mixed into mustard oil's victim is still oil, but oil added to *milk/ghee/sweets* is not an edible-oil incident → irrelevant);
- the oil is a **non-food oil** (fuel, crude, engine, hair/cosmetic, refinery);
- it is **market/price/trade** news (prices, imports, futures) with no enforcement;
- it is a **non-oil food** enforcement story (the hard negatives).

During discovery this is operationalised by a rule classifier (`classify_oil_relevance`) that assigns an **`oil_role`** and a label, before any human review or ML scoring:

| `oil_role` | Meaning | Label |
|---|---|---|
| `adulterated_product` | Edible oil is the bad product (oil term near an adulteration/enforcement term, or a strong pattern match) | **relevant** |
| `adulterant` | Oil is used to adulterate another food | irrelevant |
| `non_food_oil` | Fuel / crude / cosmetic / refinery oil | irrelevant |
| `adjacent_or_unclear` | Oil + enforcement present but role unclear, or oil with no enforcement, or price-only | manual_review / irrelevant |

The strongest 'relevant' signal is an **edible-oil term within ~90 characters of an adulteration/enforcement term** (proximity rule), or a direct phrase like *'fake oil'*, *'adulterated edible oil'*, *'oil samples failed'*. Every relevant article in the corpus additionally passed **human review**, so the training labels are human-verified, not rule-generated.

## 6. Key observations

*(Recomputed on the cleaned 486-article corpus — 139 relevant / 347 irrelevant, after the 2026-06-29 audit that removed 12 mislabelled articles and 1 duplicate. See the before/after box at the top of this report for the corpus-cleanup effect itself; these are observations about model behaviour, holding the cleaned corpus fixed.)*

**1. Embeddings beat the sparse baseline.** The best standalone embedding model (bge-large + RBF-SVM on oil-window, F1 0.823) clearly beats the best TF-IDF (0.701, `tfidf_logreg` on full-article — see also the even older `tfidf_phrase_svm` baseline in §4.1, also ~0.70). Pretrained sentence embeddings *do* help here, by a wide margin (+12 points).

**2. Ensembling is the single biggest gain.** The weighted 3-family blend (TF-IDF + bge-large-on-oil-window + RoBERTa-lead) reaches **F1 0.836** at precision 0.868 / recall 0.806 — +1.3 points over the best standalone model and +13.5 points over the TF-IDF baseline. The families are complementary: TF-IDF and bge-large contribute precision, RoBERTa contributes recall.

**3. More context still HURTS this task.** This holds up after the corpus cleanup: for every fine-tuned transformer, the lead-paragraph mode beats the full-article chunk-pooled mode — RoBERTa 0.722 vs 0.673, DistilBERT 0.657 vs 0.602, DeBERTa 0.721 vs 0.632. The oil-window-512 mode (sentences near an oil mention only) lands *between* the two for DeBERTa (0.707) but *below* chunk-pool for RoBERTa/DistilBERT, so for transformers specifically, lead-paragraph is the most reliable choice, not oil-window. The relevant signal is front-loaded in the headline/first paragraph; the article body mostly adds the shared enforcement vocabulary of the hard negatives, diluting rather than clarifying. (Longformer wasn't rerun on the cleaned corpus, but its 0.640 F1 on the original corpus — worst of all transformers despite reading all 4096 tokens — was the original evidence for this finding; see §4.1/§4 note.)

**4. For embeddings specifically, focused text > full text.** The hand-built oil-window representation (bge-large RBF-SVM, F1 0.823) beats the same model on the genuine full-article chunk-mean representation (0.800) — a 2.3-point gap. Concentrating on oil-mentioning sentences does, by hand, the filtering the model cannot learn from only ~390 training examples per fold.

**5. Frozen embeddings tolerate full text; fine-tuned transformers do not.** Embedding full-article (chunk-pooled, 0.800) is only ~2 points below oil-window, whereas transformer full-article (chunk-pool, 0.60–0.67) trails lead-paragraph (0.66–0.72) by 5–9 points. Pooling is a fixed, robust operation; a fine-tuned transformer must *learn* what to ignore, which it cannot do at this dataset size.

**6. Classifier head matters enormously for embeddings.** RBF-SVM and LogReg work well on embeddings; **Linear-SVM on embeddings collapses** (F1 0.22–0.55, recall as low as 0.13) — the bottom 12 models in the full ranking are all embedding + Linear-SVM, despite often having the *highest precision* in the whole table (up to 0.91) because they predict almost nothing positive. Calibrating a LinearSVC on dense vectors is a clear "do not do this" for this task.

**7. Precision↔recall splits cleanly by family.** Among models with usable recall, embeddings give the best precision (bge-large oil-window, P 0.826); fine-tuned transformers give the best recall (DeBERTa lead-512, R 0.885, but P only 0.609). The best ensemble (P 0.868, R 0.806) is the only model clearly above ~0.80 on **both** axes at once.

**8. Dataset size is still the binding constraint** — and slightly more so now. The cleaned corpus is 486 rows (139 relevant, down from 152), so transformers train on ~390 examples per fold with even fewer positives than before. This is consistent with frozen embedders continuing to outperform fine-tuned transformers. The path to a materially better number is **more labelled data**, not more folds, epochs, or model capacity.

**9. Longformer was dropped, not rerun, for the cleaned corpus.** Given it was already the worst transformer at F1 0.640 (original corpus) for ~16h of GPU time, and cleanup if anything raises the bar other models clear, rerunning it was not judged worth the cost. If a definitive cleaned-corpus Longformer number is needed, rerun `run_final_experiments.py` without `--skip-longformer`.

**10. Honest caveat on the headline number.** The weighted-ensemble weights are tuned on the same CV predictions they are scored on, so 0.836 is an optimistic estimate. The corresponding simple-average (untuned) figure for the same 3-family combination is **0.796** — a 4-point gap, wider than it was pre-cleanup (was 1.4 points: 0.781 avg vs 0.795 tuned). The honest range is **~0.80 (robust, e.g. the best 2-family simple average, F1 0.800) to 0.836 (tuned)**. Either end is comfortably above the TF-IDF baseline and the best standalone model.

## 7. Applying the best model to new discovery

**Note: this analysis predates the 2026-06-29 corpus cleanup** and used the
*original* best ensemble (`tfidf_logreg + e5-large_lr + roberta-base`, weights
0.31/0.37/0.31, F1 0.795 on the pre-cleanup corpus), not the current cleaned-corpus
winner (`tfidf_linsvm + bge-large_rbfsvm + roberta-base`, F1 0.836). The
saturation conclusion below is a property of the discovery space, not the
classifier, so it should still hold, but the exact probability numbers would
shift if rerun with the new ensemble checkpoint
(`scripts/score_rediscovery_with_best_ensemble.py` can be rerun against
`reports/model_training_cleaned/trained_models/final_checkpoints/` to refresh
this if needed).

The best ensemble was run on the latest discovery round (146 newly crawled articles deduplicated against all previously seen URLs):

- candidate_relevant (prob ≥ 0.76): **0**
- manual_review (0.40–0.76): **21**
- candidate_irrelevant (< 0.40): **125**

**Zero high-confidence new relevant articles** were found — the flagged items are overwhelmingly food-safety raids on non-oil products. The per-model columns show the ensemble working as designed: e5-large over-flags these (0.9+) on shared enforcement vocabulary, RoBERTa stays skeptical (~0.4–0.5), and the blend lands in the review band rather than the relevant band. This confirms the discovery space is effectively **saturated** for this query strategy.

## Appendix A — Exact keyword lexicons

*Four independent keyword sources feed different stages of the pipeline. All terms listed verbatim from source.*

### A.1 Representation lexicons (used to build oil-window & keyword-window)

**OIL_TERMS (oil-window trigger)** (16 terms) — the bare word `oil` is also matched; `ghee`/`vanaspati` deliberately excluded

```
edible oil, cooking oil, mustard oil, refined oil, palm oil, soybean oil, soya oil, groundnut oil, sesame oil, sunflower oil, rice bran oil, cottonseed oil, argemone oil, vegetable oil, canola oil, olive oil
```

**ADULTERATION_TERMS (added for keyword-window trigger)** (24 terms)

```
adulterated, adulteration, fake, spurious, misbranded, substandard, unsafe, seized, raid, raided, sample failed, failed test, food safety, FSSAI, FDA, FSDA, food adulteration, food fraud, counterfeit, sub-standard, unfit, contaminated, mislabelled, mislabeled
```

### A.2 Discovery rule-classifier lexicons (`classify_oil_relevance`)

**EDIBLE_OIL_TERMS** (18 terms) — edible-oil products in scope

```
edible oil, cooking oil, mustard oil, refined oil, soybean oil, soya oil, palm oil, groundnut oil, sesame oil, sunflower oil, rice bran oil, cottonseed oil, vegetable oil, loose oil, loose edible oil, coconut oil, olive oil, rapeseed-mustard oil
```

**ADULTERATION_ACTION_TERMS** (37 terms) — adulteration + enforcement signals

```
adulterated, adulteration, fake, spurious, contaminated, contamination, misbranded, misbranding, substandard, unsafe, rancid, seized, seizure, raid, raided, sample failed, samples failed, failed test, failed quality test, failed safety test, food safety, FSSAI, FDA, FSDA, Food Safety Department, Food Safety Officer, lab test, quality test, sample collected, samples collected, prosecution, penalty, fine, banned, shop sealed, crackdown, inspection
```

**ADULTERANT_TERMS** (6 terms) — oils that act as adulterants

```
argemone oil, mineral oil, castor oil, cottonseed oil, palmolein, cheap oil
```

**NON_FOOD_OIL_TERMS** (19 terms) — non-food oils → mark irrelevant

```
petrol, diesel, crude oil, engine oil, lubricant, kerosene, fuel adulteration, oil rig, oil rigs, oilfield, offshore oil, ONGC, oil refinery, refinery, hair oil, essential oil, massage oil, cosmetic oil, aromatherapy oil
```

**BUSINESS_ONLY_TERMS** (14 terms) — market/price/trade context → not an incident

```
oil prices, oil price, edible oil prices, oil imports, oil exports, import duty, stock market, commodity, futures, palm oil futures, soybean futures, market price, price hike, inflation
```

**NON_OIL_FOOD_TERMS** (21 terms) — other foods (the hard negatives)

```
milk, ghee, paneer, dairy products, khoya, mawa, curd, butter, cheese, spice, spices, turmeric, chilli, chili, masala, tea, honey, sweets, flour, atta, soybean corn
```

**OUT_OF_SCOPE_FOOD_TERMS** (2 terms) — excluded products

```
ghee, vanaspati
```

### A.3 Query-builder & hard-gate scorer (`config/config.yaml`)

These terms drive two things: (1) the search queries sent to GDELT / MediaCloud / RSS, and (2) a lightweight rule-based relevance score that gates articles before any ML runs. `location_terms` is a **hard filter** — an article is dropped entirely if none of these appear, regardless of other signals.

**food_terms** (19 terms)

```
edible oil, mustard oil, cooking oil, vegetable oil, palm oil, soybean oil, groundnut oil, sesame oil, sunflower oil, cottonseed oil, blended oil, rice bran oil, coconut oil, refined oil, crude palm oil, loose oil, sarson tel, rapeseed oil, linseed oil
```

**adulteration_terms** (22 terms)

```
adulteration, adulterated, fake, spurious, substandard, misbranding, mislabelling, mislabeled, unsafe, sample failure, sample failed, contaminated, contamination, impure, impurity, fraud, fraudulent, diluted, dilution, mixed with, inferior quality, unhygienic
```

**action_terms** (26 terms)

```
FSSAI, food safety, food safety department, FDA, food authority, seized, seizure, raid, raided, arrested, arrest, fine, penalty, enforcement action, crackdown, inspection, tested, lab test, laboratory, complaint, license cancelled, notice issued, show cause, legal action, police, district administration
```

**location_terms** (59 terms) — hard gate; article dropped if none present

```
India, Indian, Uttar Pradesh, UP, Maharashtra, Delhi, New Delhi, Rajasthan, Punjab, Haryana, Gujarat, Bihar, West Bengal, Madhya Pradesh, MP, Karnataka, Tamil Nadu, Kerala, Andhra Pradesh, Telangana, Odisha, Jharkhand, Assam, Chhattisgarh, Himachal Pradesh, Uttarakhand, Hyderabad, Mumbai, Kolkata, Chennai, Bengaluru, Bangalore, Jaipur, Lucknow, Kanpur, Varanasi, Patna, Noida, Gurgaon, Gurugram, Ahmedabad, Surat, Pune, Thiruvananthapuram, Kochi, Bhopal, Indore, Nagpur, Raipur, Ranchi, Guwahati, Amritsar, Ludhiana, Agra, Meerut, Barabanki, Pokaran, Jodhpur, Udaipur
```

### A.4 Iterative query-expansion novelty check (`crawler/keyword_augmentor.py`)

These are stemmed / substring-style terms used during iterative keyword augmentation to check whether a newly proposed search query overlaps meaningfully with the food-safety domain. A candidate query that matches neither list is rejected as off-topic before being added to the search queue.

**_OIL_TERMS** (19 terms)

```
oil, edible, mustard, palm, groundnut, soybean, sunflower, sesame, coconut, cottonseed, vegetable, cooking, refined, blended, rice bran, rapeseed, linseed, sarson, tel
```

**_ADULTERATION_TERMS** (29 terms) — substring / stem style

```
adulter, spurious, substandard, fake, contaminat, impure, unsafe, unhygienic, mislabel, misbranding, seized, seize, raid, fssai, fda, food safety, food inspector, crackdown, arrested, confiscated, sample fail, lab test, quality test, penalty, fine, notice, warning, banned, violation
```

### A.5 Exact model specifications

| Component | Specification |
|---|---|
| TF-IDF vectoriser | `word` n-grams (1,2) ⊕ `char_wb` n-grams (3,5), `min_df=2`, `max_df=0.95`, `sublinear_tf=True` |
| Logistic Regression | `class_weight=balanced`, `C=1.0`, `max_iter=2000`, lbfgs |
| Linear SVM | `LinearSVC` + `CalibratedClassifierCV(cv=3, sigmoid)`, balanced |
| RBF SVM | `SVC(kernel='rbf', gamma='scale', C=1.0, probability=True)`, balanced |
| Embedding encoders | all-MiniLM-L6-v2, all-mpnet-base-v2, e5-large-v2, bge-large-en-v1.5 |
| Embedding chunking | 512-token chunks, mean/max pool; StandardScaler before head |
| Transformers | distilbert-base-uncased, roberta-base, microsoft/deberta-v3-small |
| Transformer training | max 6 epochs, early stop (patience 2), lr 2e-5, fp16, class-weighted loss |
| Longformer | allenai/longformer-base-4096, up to 4096 tokens, global attention on [CLS] |
| Cross-validation | StratifiedKFold(5, shuffle=True, random_state=42) |

## 8. Outputs and artifacts

All under `news_crawler/reports/model_training_cleaned/` (cleaned corpus; original 64-model results preserved in `reports/model_training/`):

- `model_comparison.csv` — all 64 models, full metrics
- `best_model_summary.json` — winner, thresholds, full ranking
- `false_positives.csv` / `false_negatives.csv` — error cases for the best model
- `cross_validation_predictions.csv` — every per-article out-of-fold prediction
- `trained_models/final_checkpoints/` — a deployable checkpoint for every model (TF-IDF & embedding classifiers refit on full data; transformers saved from the final fold)
- `_run_state/` — per-model result cache + cached embedding matrices (made the long run resumable)

Discovery scoring: `reports/full_rediscovery/full_rediscovery_review_BEST_ensemble.xlsx` (+ `.csv`).

### Reproducibility

```
python -m src.model_training.run_final_experiments \
    --input reports/master_corpus/master_all_articles.csv \
    --label-column final_keep \
    --output-dir reports/model_training_cleaned
```

The run is resumable: finished models load from cache and are skipped, so an interrupted run continues from the last completed model.
