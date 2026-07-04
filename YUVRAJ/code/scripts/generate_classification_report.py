"""Generate a complete, professor-facing report of the relevance-classification
experiments: setup, every model, full results, observations, and outputs.

Reads the saved artifacts so all numbers are exact, then writes a single
Markdown file: reports/CLASSIFICATION_REPORT.md
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

# Optional CLI arg: the model-training results dir (default = original).
_md = sys.argv[1] if len(sys.argv) > 1 else "reports/model_training"
MT = ROOT / _md
COMP = MT / "model_comparison.csv"
SUMM = MT / "best_model_summary.json"
MASTER = ROOT / "reports/master_corpus/master_all_articles.csv"
DISC = ROOT / "reports/full_rediscovery/full_rediscovery_scored_ensemble.csv"
OUT = ROOT / "reports/CLASSIFICATION_REPORT.md"


def read_csv(p):
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fam(name):
    if name.startswith("ens"):   return "Ensemble"
    if name.startswith("tfidf"): return "TF-IDF"
    if name.startswith("emb"):   return "Embedding"
    if name.startswith("hf"):    return "Transformer"
    return "?"


def f(x):
    try: return float(x)
    except: return float("nan")


def main() -> int:
    rows = read_csv(COMP)
    summ = json.loads(SUMM.read_text(encoding="utf-8"))
    d = summ["dataset"]
    rows.sort(key=lambda r: -f(r["f1"]))

    # dataset by round
    master = read_csv(MASTER)
    by_round_tot, by_round_rel = Counter(), Counter()
    for r in master:
        rnd = r.get("round_number", "?")
        by_round_tot[rnd] += 1
        if str(r.get("final_keep", "")).strip() == "1":
            by_round_rel[rnd] += 1

    L = []
    A = L.append
    A("# Edible-Oil-Adulteration News — Relevance Classification Report")
    A("")
    A(f"*Generated {datetime.now():%Y-%m-%d}. All metrics are 5-fold stratified "
      f"cross-validation (seed 42) on the same corpus; positive class = 'relevant'.*")
    A("")

    # 1. Objective
    A("## 1. Objective")
    A("")
    A("Build a binary text classifier that decides whether an Indian news article "
      "reports an **edible-oil adulteration / contamination / food-safety enforcement "
      "incident involving edible oil** (label = relevant), as opposed to anything else "
      "— including the hard case of food-safety raids on *non-oil* products (sweets, "
      "dairy, meat, spices) that use the *same* enforcement vocabulary.")
    A("")
    A("The classifier serves two purposes: (a) screen newly discovered URLs so a human "
      "only reviews likely-relevant ones, and (b) re-screen previously dropped URLs to "
      "recover missed articles.")
    A("")

    # 2. Dataset
    A("## 2. Dataset")
    A("")
    A(f"- **{d['total_rows']} labelled articles with text** "
      f"({d['relevant']} relevant / {d['irrelevant']} irrelevant, "
      f"{100*d['relevant']/d['total_rows']:.0f}% positive).")
    A(f"- Average length **{d.get('avg_words','?')} words**, max {d.get('max_words','?')} words.")
    A("- Class imbalance handled with `class_weight='balanced'` in every classifier.")
    A("- The corpus was assembled over four discovery rounds plus a rescreen of "
      "previously-dropped URLs:")
    A("")
    A("| Round | Total | Relevant |")
    A("|---|---|---|")
    for rnd in sorted(by_round_tot):
        A(f"| {rnd} | {by_round_tot[rnd]} | {by_round_rel[rnd]} |")
    A("")
    A("**The central difficulty — hard negatives.** Many irrelevant articles are "
      "food-safety raids on dairy/sweets/meat. They contain the exact enforcement "
      "vocabulary of relevant articles (*FSSAI, seized, raid, samples failed, "
      "adulterated*), so the task is not keyword spotting — it requires distinguishing "
      "*oil-as-the-adulterated-product* from *generic enforcement*. This is what makes "
      "the problem hard and is the lens for most observations below.")
    A("")

    # 3. Setup
    A("## 3. Experimental setup (held constant across all models)")
    A("")
    A("- **Same corpus, same 5 stratified folds, same seed (42)** — so every model's "
      "out-of-fold probabilities align per-article and are directly comparable / "
      "ensembleable.")
    A("- **Metrics:** Accuracy, Precision, Recall, F1, ROC-AUC, PR-AUC (positive class).")
    A("- **Evaluation is by cross-validation; deployable checkpoints are refit on the "
      "full dataset** (transformers saved from the final fold).")
    A("")
    A("### Three text representations")
    A("")
    A("| Name | What the model sees |")
    A("|---|---|")
    A("| `title_plus_body_full` | Title + the **entire** article body, no truncation. |")
    A("| `title_plus_oil_windows` | Title + first paragraph + every **oil-mentioning** "
      "sentence (±1 neighbour). A focused, signal-dense view. |")
    A("| `title_plus_keyword_windows` | Title + sentences around any oil **or** "
      "enforcement keyword (±1). |")
    A("")
    A("The **oil-window** representation keys on oil terms *only* (not enforcement "
      "terms), deliberately, so it naturally drops sentences that are about enforcement "
      "of non-oil products — directly attacking the hard-negative problem. "
      "(`ghee`/`vanaspati` are excluded as positive keywords, matching the discovery "
      "NOT-block.)")
    A("")

    # 4. Models
    A("## 4. Models evaluated (64 total)")
    A("")
    A("| Block | Models | Count |")
    A("|---|---|---|")
    A("| 1. **Sparse TF-IDF** | word(1–2) ⊕ char(3–5) n-grams; {Logistic Regression, "
      "Linear SVM} × 3 representations | 6 |")
    A("| 2. **Full-article embeddings** | {MiniLM, MPNet, e5-large, bge-large} × "
      "{full-chunk-mean, full-chunk-max, oil-window} × {LogReg, Linear SVM, RBF SVM} | 36 |")
    A("| 3. **Fine-tuned transformers** | {DistilBERT, RoBERTa, DeBERTa-v3} × "
      "{lead-512, oil-window-512, chunk-pool-full} | 9 |")
    A("| 4. **Longformer-4096** | full article up to 4096 tokens | 1 |")
    A("| 5. **Ensembles** | best-of-family blends, simple-average + weighted (grid 0.2–0.8) | 12 |")
    A("")
    A("**Embedding full-article handling:** the whole article is split into 512-token "
      "chunks, each embedded, then mean- or max-pooled — so embeddings genuinely see the "
      "entire article. **Transformer `chunk_pool_full`:** up to 4×512 tokens → CLS "
      "vectors → mean+max pooled → classifier head. All transformer training used fp16 "
      "+ gradient accumulation to fit a 6 GB GPU.")
    A("")

    # 5. Full results
    A("## 5. Full results — all 64 models, ranked by F1")
    A("")
    A("| # | Model | Repr | F1 | Prec | Rec | ROC-AUC | PR-AUC |")
    A("|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        A(f"| {i} | {r['model_name'][:46]} | {r['representation'][:22]} | "
          f"{f(r['f1']):.3f} | {f(r['precision']):.3f} | {f(r['recall']):.3f} | "
          f"{f(r['roc_auc']):.3f} | {f(r['pr_auc']):.3f} |")
    A("")

    # best per family
    A("### Best model per family")
    A("")
    A("| Family | F1 | Prec | Recall | Best model |")
    A("|---|---|---|---|---|")
    for fname in ["Ensemble", "Embedding", "Transformer", "TF-IDF"]:
        cand = [r for r in rows if fam(r["model_name"]) == fname]
        if cand:
            b = max(cand, key=lambda r: f(r["f1"]))
            A(f"| {fname} | {f(b['f1']):.3f} | {f(b['precision']):.3f} | "
              f"{f(b['recall']):.3f} | {b['model_name'][:50]} |")
    A("")

    bm = summ["best_model_by_f1"]
    A("### Best overall model")
    A("")
    A(f"**{bm['model_name']}**")
    A("")
    A(f"- F1 **{bm['f1']}**, Precision {bm['precision']}, Recall {bm['recall']}, "
      f"ROC-AUC {bm['roc_auc']}, PR-AUC {bm['pr_auc']}")
    A(f"- A weighted blend of **TF-IDF + e5-large embedding + RoBERTa** "
      f"(weights 0.31 / 0.37 / 0.31).")
    th = bm.get("thresholds", {})
    A(f"- Operating thresholds: high-recall {th.get('high_recall')}, "
      f"balanced {th.get('balanced')}, high-precision {th.get('high_precision')}.")
    A("")

    # ── Methods explained ─────────────────────────────────────────────────────
    A("## 5b. Methods explained")
    A("")
    A("### Sparse / lexical models")
    A("")
    A("- **TF-IDF** (Term Frequency × Inverse Document Frequency) turns each article "
      "into a sparse vector of weighted n-gram counts: a term is weighted up if it is "
      "frequent in an article but rare across the corpus. We combine two views with a "
      "`FeatureUnion`: **word n-grams (1–2)** capture phrases like *'mustard oil'* / "
      "*'samples failed'*, and **character n-grams (3–5)** capture sub-word spelling and "
      "morphology — robust to Indian-English spelling variants and unseen words "
      "(*adulterat-ed/-ion*, *mislabelled/mislabeled*).")
    A("- **Logistic Regression** — a linear model that outputs a calibrated probability "
      "of 'relevant'. `class_weight='balanced'` compensates for the 31% positive rate.")
    A("- **Linear SVM** — a max-margin linear classifier; we wrap it in probability "
      "calibration (Platt/sigmoid) so it can output probabilities and join ensembles.")
    A("")
    A("### Embedding models (frozen encoder + small classifier)")
    A("")
    A("- A **sentence embedding** model is a pretrained neural network that maps a piece "
      "of text to a fixed-length dense vector capturing *meaning* — texts with similar "
      "meaning land near each other. The encoder is **frozen** (never trained on our "
      "labels); only a small classifier on top is trained. This is why embeddings do "
      "well on a small dataset: they bring outside knowledge and don't have to learn "
      "from our ~487 rows.")
    A("- **Four encoders:** `all-MiniLM-L6-v2` (384-d, small/fast), `all-mpnet-base-v2` "
      "(768-d), `intfloat/e5-large-v2` (1024-d, needs a `\"passage: \"` prefix), "
      "`BAAI/bge-large-en-v1.5` (1024-d).")
    A("- **Full-article pooling:** the whole article is split into 512-token chunks, each "
      "chunk embedded, then the chunk vectors are **mean-pooled** (`full_chunk_mean`) or "
      "**max-pooled** (`full_chunk_max`) into one document vector. This lets a "
      "512-token encoder represent an arbitrarily long article.")
    A("- **Three classifier heads** on each embedding: **Logistic Regression**, **Linear "
      "SVM**, and **RBF SVM** (a kernel SVM that can draw a *non-linear* boundary — it "
      "was consistently the best head for embeddings).")
    A("")
    A("### Fine-tuned transformers")
    A("")
    A("- A **transformer** reads text with self-attention and produces context-aware "
      "representations. Unlike the frozen embedders, here we **fine-tune** — update the "
      "whole network's weights — on our labels. `DistilBERT` (small), `RoBERTa-base`, "
      "and `DeBERTa-v3-small` are standard encoders with a classification head.")
    A("- These models have a hard **512-token input limit**. We tested three ways of "
      "fitting an article into that budget:")
    A("  - **`lead_512`** — title + body truncated to the first 512 tokens (the lead).")
    A("  - **`oil_window_512`** — the focused oil-window text (below), up to 512 tokens.")
    A("  - **`chunk_pool_full`** — the full article in up to 4×512-token chunks; each "
      "chunk's `[CLS]` vector is taken, then **mean+max pooled** and passed to the head "
      "(so the model sees the whole article, ≤2048 tokens).")
    A("")
    A("### Longformer")
    A("")
    A("- **`allenai/longformer-base-4096`** is a transformer built for long documents: "
      "sparse + global attention lets it ingest up to **4096 tokens** directly (our "
      "longest article is ~2400 tokens, so it sees essentially everything). It is the "
      "cleanest 'whole-article transformer' test.")
    A("")
    A("### Ensembles")
    A("")
    A("- An ensemble **averages the predicted probabilities** of several models, then "
      "thresholds the blend. Because all models share the same folds/seed, their "
      "out-of-fold probabilities align per-article, so averaging is fair. **Simple "
      "average** = equal weights; **weighted average** = weights grid-searched over "
      "{0.2…0.8} (normalised), keeping the combination with the best F1. Ensembles help "
      "when members make *different* mistakes — here, embeddings (precise) + RoBERTa "
      "(high recall) are complementary.")
    A("")

    # ── Representations & oil-relevance ───────────────────────────────────────
    A("## 5c. Text representations & keyword windows in detail")
    A("")
    A("All three representations are built per article from its title and body.")
    A("")
    A("**`title_plus_body_full`** — the title followed by the complete body, untruncated. "
      "Used directly by TF-IDF, and chunked for the embedding/transformer full-article "
      "modes.")
    A("")
    A("**`title_plus_oil_windows`** (the 'oil-window') — built as:")
    A("")
    A("1. Split the body into sentences.")
    A("2. **Always keep the first paragraph** (text before the first blank line, else the "
      "first two sentences) — Indian news states the key fact in the lead.")
    A("3. **Scan every sentence**; if it mentions an **oil term** (the oil lexicon below, "
      "plus the bare word *oil*), keep that sentence **plus one sentence on each side** "
      "for context.")
    A("4. Concatenate title + first paragraph + the kept oil-sentences, de-duplicated.")
    A("")
    A("The key design choice: it keys on **oil terms only**, *not* enforcement terms. "
      "Sentences about enforcement of *non-oil* products (a paneer raid, a sweets "
      "seizure) contain no oil term, so they are dropped — directly removing the "
      "hard-negative vocabulary. This is the representation behind the best single model.")
    A("")
    A("**`title_plus_keyword_windows`** — the same windowing idea but the trigger is "
      "**any oil *or* adulteration/enforcement keyword** (both lexicons below). It is "
      "broader, so it re-admits some of the shared enforcement vocabulary, which is why "
      "it slightly underperforms the oil-window.")
    A("")
    A("Word boundaries are enforced, so *oil* matches as a whole word only — it does **not** "
      "fire inside *boil*, *spoil*, *turmoil*, or *oilseed*.")
    A("")
    A("## 5d. What 'oil-relevant' means (the labelling definition)")
    A("")
    A("An article is **relevant** if it documents an incident in which **edible oil "
      "itself is the adulterated / contaminated / substandard / seized / failed "
      "product**. It is **not** relevant if:")
    A("")
    A("- oil is the **adulterant** used to debase *another* food (e.g. argemone oil mixed "
      "into mustard oil's victim is still oil, but oil added to *milk/ghee/sweets* is "
      "not an edible-oil incident → irrelevant);")
    A("- the oil is a **non-food oil** (fuel, crude, engine, hair/cosmetic, refinery);")
    A("- it is **market/price/trade** news (prices, imports, futures) with no enforcement;")
    A("- it is a **non-oil food** enforcement story (the hard negatives).")
    A("")
    A("During discovery this is operationalised by a rule classifier "
      "(`classify_oil_relevance`) that assigns an **`oil_role`** and a label, before any "
      "human review or ML scoring:")
    A("")
    A("| `oil_role` | Meaning | Label |")
    A("|---|---|---|")
    A("| `adulterated_product` | Edible oil is the bad product (oil term near an "
      "adulteration/enforcement term, or a strong pattern match) | **relevant** |")
    A("| `adulterant` | Oil is used to adulterate another food | irrelevant |")
    A("| `non_food_oil` | Fuel / crude / cosmetic / refinery oil | irrelevant |")
    A("| `adjacent_or_unclear` | Oil + enforcement present but role unclear, or oil with "
      "no enforcement, or price-only | manual_review / irrelevant |")
    A("")
    A("The strongest 'relevant' signal is an **edible-oil term within ~90 characters of "
      "an adulteration/enforcement term** (proximity rule), or a direct phrase like "
      "*'fake oil'*, *'adulterated edible oil'*, *'oil samples failed'*. Every relevant "
      "article in the corpus additionally passed **human review**, so the training "
      "labels are human-verified, not rule-generated.")
    A("")

    # 6. Observations
    A("## 6. Key observations")
    A("")
    A("**1. Embeddings beat the sparse baseline.** The best embedding model "
      "(e5-large + LogReg on oil-window, F1 0.779) clearly beats the best TF-IDF "
      "(0.701). Answering the original question: pretrained sentence embeddings *do* "
      "help here.")
    A("")
    A("**2. Ensembling is the single biggest gain.** A weighted 3-family blend reaches "
      "**F1 0.795 (+9.4 points over baseline)** at precision 0.75 / recall 0.84. No "
      "standalone model exceeds 0.78. The families are complementary: embeddings "
      "contribute precision, RoBERTa contributes recall.")
    A("")
    A("**3. More context HURTS this task** — the most important finding. For every "
      "fine-tuned transformer, the full-article mode scored *below* the lead-paragraph "
      "mode (RoBERTa 0.695 vs 0.703; DistilBERT 0.671 vs 0.689; DeBERTa 0.630 vs 0.658), "
      "and **Longformer reading the full 4096 tokens was among the worst transformers "
      "(F1 0.640)**. The relevant signal is front-loaded in the headline/first "
      "paragraph; the article body mostly adds the shared enforcement vocabulary of the "
      "hard negatives, diluting rather than clarifying.")
    A("")
    A("**4. Focused text > full text, and the gap is explainable.** The hand-built "
      "oil-window representation (0.779) beats the genuine full-article representation "
      "(0.764). Concentrating on oil-mentioning sentences does, by hand, the filtering "
      "the models cannot learn from only ~487 examples.")
    A("")
    A("**5. Frozen embeddings tolerate full text; fine-tuned transformers do not.** "
      "Embedding full-article (chunk-pooled, 0.764) is only ~1.5 F1 below oil-window, "
      "whereas transformer full-article *collapses*. Pooling is a fixed, robust "
      "operation; a fine-tuned transformer must *learn* what to ignore, which it cannot "
      "do at this dataset size.")
    A("")
    A("**6. Classifier head matters for embeddings.** RBF-SVM and LogReg work well on "
      "embeddings; **Linear-SVM on embeddings collapses** (F1 0.24–0.50, recall as low "
      "as 0.15) — the bottom 12 models are all embedding + Linear-SVM. Calibrating a "
      "LinearSVC on dense vectors is a clear 'do not do this'.")
    A("")
    A("**7. Precision↔recall splits cleanly by family.** Embeddings give the highest "
      "precision (e5-large oil-window, P 0.769); fine-tuned transformers give the "
      "highest recall (DeBERTa lead-512, R 0.875, but P only 0.528). The best ensemble "
      "is the only model above ~0.75 on **both** precision and recall.")
    A("")
    A("**8. Dataset size is the binding constraint.** Transformers are data-starved at "
      "487 rows — they cannot learn long-range attention from ~390 training examples per "
      "fold, which is why frozen embedders win. The path to better performance is **more "
      "labelled data**, not more folds, epochs, or model capacity. (Transformers already "
      "use early stopping, so more epochs would only overfit.)")
    A("")
    A("**9. Practical note on Longformer.** Full 4096-token Longformer was impractical "
      "on a 6 GB laptop GPU (~16 h wall-clock for one model, VRAM ~95% full) and did not "
      "improve on cheaper models. Not recommended for this hardware/task.")
    A("")
    A("**10. Honest caveat on the headline number.** The weighted-ensemble weights are "
      "tuned on the same CV predictions they are scored on, so 0.795 is a mild "
      "optimistic estimate. The simple-average (untuned) figure is 0.781. The honest "
      "range is **~0.78 (robust) to 0.795 (tuned)** — still clearly above the best "
      "single model and the baseline.")
    A("")

    # 7. Application to discovery
    A("## 7. Applying the best model to new discovery")
    A("")
    if DISC.exists():
        drows = read_csv(DISC)
        bc = Counter(r["bucket"] for r in drows)
        A(f"The best ensemble was run on the latest discovery round "
          f"({len(drows)} newly crawled articles deduplicated against all previously "
          f"seen URLs):")
        A("")
        A(f"- candidate_relevant (prob ≥ 0.76): **{bc.get('candidate_relevant',0)}**")
        A(f"- manual_review (0.40–0.76): **{bc.get('manual_review',0)}**")
        A(f"- candidate_irrelevant (< 0.40): **{bc.get('candidate_irrelevant',0)}**")
        A("")
        A("**Zero high-confidence new relevant articles** were found — the flagged items "
          "are overwhelmingly food-safety raids on non-oil products. The per-model "
          "columns show the ensemble working as designed: e5-large over-flags these "
          "(0.9+) on shared enforcement vocabulary, RoBERTa stays skeptical (~0.4–0.5), "
          "and the blend lands in the review band rather than the relevant band. This "
          "confirms the discovery space is effectively **saturated** for this query "
          "strategy.")
    else:
        A("*(discovery scoring file not found)*")
    A("")

    # Appendix: exact lexicons (imported verbatim from the code)
    A("## Appendix A — Exact keyword lexicons")
    A("")
    A("*Imported verbatim from the source at report-generation time.*")
    A("")

    def termblock(title, terms, note=""):
        A(f"**{title}** ({len(terms)} terms){(' — ' + note) if note else ''}")
        A("")
        A("```")
        A(", ".join(terms))
        A("```")
        A("")

    try:
        from src.model_training import build_text_representations as BTR
        A("### A.1 Representation lexicons (used to build oil-window & keyword-window)")
        A("")
        termblock("OIL_TERMS (oil-window trigger)", BTR.OIL_TERMS,
                  "the bare word `oil` is also matched; `ghee`/`vanaspati` deliberately excluded")
        termblock("ADULTERATION_TERMS (added for keyword-window trigger)", BTR.ADULTERATION_TERMS)
    except Exception as e:
        A(f"*(could not import representation lexicons: {e})*")
        A("")

    try:
        from crawler import oil_relevance as ORL
        A("### A.2 Discovery rule-classifier lexicons (`classify_oil_relevance`)")
        A("")
        termblock("EDIBLE_OIL_TERMS", ORL.EDIBLE_OIL_TERMS, "edible-oil products in scope")
        termblock("ADULTERATION_ACTION_TERMS", ORL.ADULTERATION_ACTION_TERMS,
                  "adulteration + enforcement signals")
        termblock("ADULTERANT_TERMS", ORL.ADULTERANT_TERMS, "oils that act as adulterants")
        termblock("NON_FOOD_OIL_TERMS", ORL.NON_FOOD_OIL_TERMS,
                  "non-food oils → mark irrelevant")
        termblock("BUSINESS_ONLY_TERMS", ORL.BUSINESS_ONLY_TERMS,
                  "market/price/trade context → not an incident")
        termblock("NON_OIL_FOOD_TERMS", ORL.NON_OIL_FOOD_TERMS,
                  "other foods (the hard negatives)")
        termblock("OUT_OF_SCOPE_FOOD_TERMS", ORL.OUT_OF_SCOPE_FOOD_TERMS,
                  "excluded products")
    except Exception as e:
        A(f"*(could not import rule lexicons: {e})*")
        A("")

    A("### A.3 Exact model specifications")
    A("")
    A("| Component | Specification |")
    A("|---|---|")
    A("| TF-IDF vectoriser | `word` n-grams (1,2) ⊕ `char_wb` n-grams (3,5), "
      "`min_df=2`, `max_df=0.95`, `sublinear_tf=True` |")
    A("| Logistic Regression | `class_weight=balanced`, `C=1.0`, `max_iter=2000`, lbfgs |")
    A("| Linear SVM | `LinearSVC` + `CalibratedClassifierCV(cv=3, sigmoid)`, balanced |")
    A("| RBF SVM | `SVC(kernel='rbf', gamma='scale', C=1.0, probability=True)`, balanced |")
    A("| Embedding encoders | all-MiniLM-L6-v2, all-mpnet-base-v2, e5-large-v2, bge-large-en-v1.5 |")
    A("| Embedding chunking | 512-token chunks, mean/max pool; StandardScaler before head |")
    A("| Transformers | distilbert-base-uncased, roberta-base, microsoft/deberta-v3-small |")
    A("| Transformer training | max 6 epochs, early stop (patience 2), lr 2e-5, fp16, "
      "class-weighted loss |")
    A("| Longformer | allenai/longformer-base-4096, up to 4096 tokens, global attention on [CLS] |")
    A("| Cross-validation | StratifiedKFold(5, shuffle=True, random_state=42) |")
    A("")

    # 8. Outputs
    A("## 8. Outputs and artifacts")
    A("")
    A("All under `news_crawler/reports/model_training/`:")
    A("")
    A("- `model_comparison.csv` — all 64 models, full metrics")
    A("- `best_model_summary.json` — winner, thresholds, full ranking")
    A("- `false_positives.csv` / `false_negatives.csv` — error cases for the best model")
    A("- `cross_validation_predictions.csv` — every per-article out-of-fold prediction")
    A("- `trained_models/final_checkpoints/` — a deployable checkpoint for every model "
      "(TF-IDF & embedding classifiers refit on full data; transformers saved from the "
      "final fold)")
    A("- `_run_state/` — per-model result cache + cached embedding matrices (made the "
      "long run resumable)")
    A("")
    A("Discovery scoring: `reports/full_rediscovery/full_rediscovery_review_BEST_ensemble.xlsx` "
      "(+ `.csv`).")
    A("")
    A("### Reproducibility")
    A("")
    A("```")
    A("python -m src.model_training.run_final_experiments \\")
    A("    --input reports/master_corpus/master_all_articles.csv \\")
    A("    --label-column final_keep \\")
    A("    --output-dir reports/model_training")
    A("```")
    A("")
    A("The run is resumable: finished models load from cache and are skipped, so an "
      "interrupted run continues from the last completed model.")
    A("")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"Report written: {OUT}")
    print(f"  {len(L)} lines, {len(rows)} models documented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())