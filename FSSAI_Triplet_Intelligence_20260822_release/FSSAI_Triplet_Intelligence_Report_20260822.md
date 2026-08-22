# Food-Specific Triplet Intelligence from the FSSAI Baseline and News

## Oil, Ghee and Milk | Local-data-only research report | 22 August 2026

## Abstract

This report compares **13,355 FSSAI baseline triplets** with **14,954 triplets extracted from Oil, Ghee and Milk news articles**. All retained news triplets are included without using historical adjudication labels; model confidence is the only model-derived quality variable. The analysis asks four questions: what structured relations dominate official and incident-oriented knowledge, which food-adulterant and food-test relationships are not represented in the FSSAI baseline, what health and enforcement signals occur in news, and whether compatible graph paths support food-adulterant-effect causal hypotheses.

The graph contains **3,168 direct news food-adulterant/substitute rows**, **1,229 news effect rows**, and **481 food-adulterant-effect combinations with at least one directly joined same-article chain**. The strongest requested example is Milk -> ethylene glycol -> renal failure: 23 articles contain the directly joinable chain. In the reverse article-context analysis, 23 of 41 Milk articles carrying renal-failure context and at least one explicit food-adulterant relation also name ethylene glycol (56.1%; Laplace-smoothed 55.8%). This is useful for hypothesis ranking but is not a calibrated diagnostic probability and may reflect repeated coverage of one incident.

## Evidence boundary

No internet, external database, chemical handbook, clinical reference, regulatory webpage or unstored source is used. Every descriptive claim comes from the supplied CSV/JSONL files or from deterministic joins over those files. Recommendations about validation design are methodological proposals. A missing relationship means **not represented in the supplied FSSAI baseline**, not proven absent from all current FSSAI documents.

## Executive findings

1. The combined corpus contains **28,309 rows**, but only **6 exact normalized triplets** overlap. The main reason is functional: the FSSAI baseline emphasizes definitions, ingredients, functions, standards, limits and obligations, while news emphasizes adulterants, health effects, actors, places, methods and actions.
2. News contributes **11,582 normalized triplets** and **9,043 entities not exactly represented in the baseline. These are discovery leads, not automatically validated additions.
3. Leading food-specific candidate gaps include Ghee -> palm oil family, Milk -> urea, Milk -> ethylene glycol, Milk -> detergent, Milk -> starch, Paneer -> starch, Khoya/mawa -> starch, Paneer -> detergent. Each is ranked using confidence, unique-article recurrence, locally linked health evidence, baseline pair coverage and method coverage.
4. The graph supports explicit causal-chain analysis. Milk -> ethylene glycol -> renal failure is the dominant directly joined chain, followed by Milk -> ethylene glycol -> multi-organ failure and Milk -> ethylene glycol -> anuria.
5. Candidate food specificity is material. Ethylene glycol is concentrated in Milk (34 articles; 81.0%), cough syrup (2 articles; 4.8%), Curd/yoghurt (1 articles; 2.4%), syrup (1 articles; 2.4%), propylene glycol (1 articles; 2.4%). It should not be assigned equal prior relevance to Oil, Ghee and Milk.
6. Confidence is high and compressed: news mean 0.8873, median 0.90. Therefore confidence supports ranking but cannot substitute for entity resolution, incident deduplication, laboratory confirmation or causal validation.

## 1. Research questions

The analysis is designed around structured questions rather than a list of chemical names:

- Which subject-predicate-object relations are shared or unique across the FSSAI baseline and news?
- Which candidate adulterants are connected to which foods, and how often across distinct articles?
- Does the FSSAI baseline represent the exact food-adulterant pair, only the candidate in another role, or neither?
- Does either graph represent a candidate-specific detection method?
- Which effects are directly attributed to adulterants, and which are only contextually associated within an article?
- Given a food and observed effect, which candidate adulterants are most frequently co-represented?
- Is a candidate food-specific or spread across several food matrices?
- Which graph gaps should be routed to document verification, method validation or targeted surveillance?

## 2. Data inventory

| Corpus | Rows | Unique triplets | Entities | Sources | Mean confidence |
| --- | --- | --- | --- | --- | --- |
| FSSAI baseline | 13,355 | 12,388 | 9,603 | 27 | 0.9415 |
| News | 14,954 | 11,588 | 9,470 | 1,970 | 0.8873 |

| Pool | Input articles | Articles represented | Triplet rows | Mean confidence | Rows >=0.90 |
| --- | --- | --- | --- | --- | --- |
| Oil | 621 | 519 | 3260 | 0.8845 | 1956 |
| Ghee | 1015 | 933 | 6907 | 0.8866 | 4290 |
| Milk | 1150 | 518 | 4787 | 0.8903 | 3123 |

The news export represents 1,970 article-food records across the three pools. Articles with no retained triplets remain part of corpus-coverage accounting but cannot contribute edges. The FSSAI baseline has 27 source IDs and is treated as a verified reference graph, not as a probabilistic news model output.

![Comparable corpus scale](figures\figure_01_corpus_scale.png)

*Figure 1. All retained news triplets are included; no status-based partition is used.*

![Knowledge-graph breadth](figures\figure_02_graph_breadth.png)

*Figure 2. The corpora are similar in row scale but encode different knowledge functions.*

## 3. Common schema and provenance

The new FSSAI baseline, News and Combined CSVs use the same 14 columns: snippet and source identifiers, source file/type, chunk index, subject/type/ID, predicate, object/type/ID, confidence and evidence span. The news `source_file` field contains the article URL. A companion provenance file adds corpus, food pool, title, date, publisher, canonical fields and a stable triplet ID. Raw values are retained; normalization never overwrites source assertions.

Historical triplet-status labels are absent from the new CSVs, workbook and analysis. Every retained news row participates. Rejected candidates are not reconstructed because they are not present in the retained input export.

## 4. Confidence policy and sensitivity

All 14,954 news rows and all 13,355 FSSAI baseline rows carry a finite confidence value. News values range from 0.45 to 0.98. Counts are always reported independently from confidence. A confidence-weighted source-support measure sums the maximum confidence per source so repeated rows from one article do not contribute linearly without bound.

Confidence is not assumed calibrated across predicates, foods or models. Sensitivity tables show all rows and minimum thresholds of 0.70, 0.80, 0.90 and 0.95. The main report uses all triplets as requested.

![Confidence distributions](figures\figure_03_confidence_distribution.png)

*Figure 3. Confidence is preserved as supplied and is the only model-quality signal used for news rankings.*

![News confidence by food pool](figures\figure_04_confidence_by_food.png)

*Figure 4. The three pools have similar confidence distributions; counts and food-specific evidence drive substantive differences.*

![Sensitivity to confidence thresholds](figures\figure_28_confidence_sensitivity.png)

*Figure 28. Threshold views are reported alongside the all-triplet result; no historical status field is used.*

## 5. Combined knowledge-graph landscape

The FSSAI baseline contains 12,382 normalized triples not found exactly in news; news contains 11,582 not found exactly in the baseline. Only 427 normalized entity strings overlap. Exact comparison is deliberately conservative and exposes the need for identifiers: all source rows leave subject and object IDs blank, so synonym resolution currently depends on text normalization and audited alias maps.

![Dominant predicates reveal different corpus functions](figures\figure_06_predicate_comparison.png)

*Figure 6. FSSAI baseline emphasizes standards and definitions; news emphasizes incidents, adulterants, effects, places and actions.*

![Normalized overlap is sparse](figures\figure_07_overlap.png)

*Figure 7. Exact overlap is conservative; terminology and role differences can hide contextual overlap.*

The sparse overlap does not mean the FSSAI baseline is irrelevant to news. It means the graphs often encode different sides of the same problem. The baseline may define a food, limit or method while news supplies an incident, adulterant, effect, actor or action. The useful unit of gap analysis is therefore **food + candidate + role + method + effect + evidence**, not term presence alone.

## 6. News-only triplet landscape

News contains 3,168 direct `hasAdulterant` or `isSubstituteFor` rows. The analysis collapses exact duplicate mentions at several levels: row count, unique canonical relation, unique article and confidence-weighted article support. Article counts remain reporting counts and may still describe repeated coverage of one incident.

![News-triplet coverage by food pool](figures\figure_05_food_pool_coverage.png)

*Figure 5. Article counts measure corpus representation, not incident prevalence.*

![Most reported food-adulterant relationships](figures\figure_08_top_food_adulterants.png)

*Figure 8. Ranks use unique articles and retain the explicitly named affected food.*

![Food-specific adulterant article matrix](figures\figure_12_food_adulterant_heatmap.png)

*Figure 12. The same candidate is not assumed equally likely across foods.*

![Recurrence and confidence are complementary signals](figures\figure_13_recurrence_confidence.png)

*Figure 13. Confidence ranks extraction certainty; recurrence measures corpus repetition and can include duplicate incident coverage.*

## Oil: food-specific news findings

The Oil pool contains **3,260 triplet rows** from **519 represented articles** out of 621 inputs. Its mean confidence is 0.8845. The table below uses the food explicitly named in each triplet; it does not relabel every relation according to the collection name.

| Affected food | Candidate | Rows | Articles | Mean confidence | Weighted support |
| --- | --- | --- | --- | --- | --- |
| Sunflower oil | palm oil family | 13 | 10 | 0.9 | 8.9 |
| Mustard oil | argemone oil | 9 | 8 | 0.9333 | 7.5 |
| Mustard oil | rice bran oil | 11 | 6 | 0.9136 | 5.6 |
| Soybean oil | palm oil family | 5 | 4 | 0.94 | 3.8 |
| Mustard oil | palm oil family | 6 | 4 | 0.9 | 3.6 |
| Coconut oil | palm oil family | 6 | 4 | 0.8667 | 3.5 |
| Edible/cooking oil | used cooking oil | 3 | 3 | 0.8833 | 2.65 |
| Edible/cooking oil | total polar compounds | 4 | 3 | 0.875 | 2.65 |
| Mustard oil | artificial colours | 2 | 2 | 0.95 | 1.9 |
| edible oils | machine oil | 2 | 2 | 0.95 | 1.9 |
| olive oil | chlorophyll | 2 | 2 | 0.95 | 1.9 |
| olive oil | denatured rapeseed oil | 3 | 2 | 0.95 | 1.9 |
| Groundnut oil | palm oil family | 3 | 2 | 0.9333 | 1.9 |
| Edible/cooking oil | dust | 2 | 2 | 0.925 | 1.85 |
| Edible/cooking oil | sand | 2 | 2 | 0.925 | 1.85 |

Leading candidate baseline gaps for this food scope are: Sunflower oil -> palm oil family (10 articles, confidence 0.9); Edible/cooking oil -> total polar compounds (3 articles, confidence 0.875); Soybean oil -> palm oil family (4 articles, confidence 0.94); edible oils -> heavy metals (2 articles, confidence 0.9); edible oils -> pesticide residue (2 articles, confidence 0.9); Mustard oil -> palm oil family (4 articles, confidence 0.9).

![Most reported relationships in the Oil article pool](figures\figure_09_top_oil.png)

*Figure 9. Food is taken from the triplet; the pool only identifies the source collection.*
## Ghee: food-specific news findings

The Ghee pool contains **6,907 triplet rows** from **933 represented articles** out of 1,015 inputs. Its mean confidence is 0.8866. The table below uses the food explicitly named in each triplet; it does not relabel every relation according to the collection name.

| Affected food | Candidate | Rows | Articles | Mean confidence | Weighted support |
| --- | --- | --- | --- | --- | --- |
| Ghee | animal fat | 139 | 102 | 0.8824 | 90.75 |
| Ghee | palm oil family | 184 | 100 | 0.9117 | 91.7 |
| Ghee | vegetable oil/fat | 124 | 73 | 0.9042 | 67.1 |
| Ghee | vanaspati | 41 | 32 | 0.9061 | 29.15 |
| Ghee | lard/pig fat | 31 | 27 | 0.8839 | 23.95 |
| Ghee | beef tallow | 27 | 24 | 0.8611 | 20.75 |
| Ghee | acetic acid ester | 22 | 19 | 0.9045 | 17.2 |
| Ghee | fish oil | 20 | 19 | 0.8875 | 16.9 |
| Ghee | beta carotene | 16 | 15 | 0.8938 | 13.45 |
| Ghee | starch | 12 | 11 | 0.8708 | 9.65 |
| Ghee | coconut oil | 13 | 10 | 0.8923 | 8.95 |
| Ghee | refined oil | 10 | 9 | 0.92 | 8.3 |
| Ghee | fake ghee | 11 | 9 | 0.8818 | 7.95 |
| Ghee | soybean oil | 9 | 8 | 0.8944 | 7.15 |
| Ghee | synthetic ghee | 10 | 7 | 0.92 | 6.5 |

Leading candidate baseline gaps for this food scope are: Ghee -> palm oil family (100 articles, confidence 0.9117); Ghee -> starch (11 articles, confidence 0.8708); Ghee -> urea (3 articles, confidence 0.9); Ghee -> vegetable oil/fat (73 articles, confidence 0.9042); Ghee -> animal fat (102 articles, confidence 0.8824); Ghee -> detergent (1 articles, confidence 0.9).

![Most reported relationships in the Ghee article pool](figures\figure_10_top_ghee.png)

*Figure 10. Food is taken from the triplet; the pool only identifies the source collection.*
## Milk: food-specific news findings

The Milk pool contains **4,787 triplet rows** from **518 represented articles** out of 1,150 inputs. Its mean confidence is 0.8903. The table below uses the food explicitly named in each triplet; it does not relabel every relation according to the collection name.

| Affected food | Candidate | Rows | Articles | Mean confidence | Weighted support |
| --- | --- | --- | --- | --- | --- |
| Milk | urea | 49 | 42 | 0.9286 | 39.1 |
| Milk | detergent | 39 | 35 | 0.9231 | 32.55 |
| Milk | ethylene glycol | 46 | 34 | 0.9315 | 31.9 |
| Milk | starch | 30 | 28 | 0.9317 | 26.1 |
| Milk | water | 34 | 26 | 0.9176 | 24.1 |
| Milk | edible oil | 18 | 12 | 0.8917 | 10.9 |
| Milk | palm oil family | 16 | 12 | 0.8812 | 10.7 |
| Milk | vegetable oil/fat | 13 | 10 | 0.8923 | 9.05 |
| Milk | hydrogen peroxide | 10 | 9 | 0.945 | 8.5 |
| Milk | refined oil | 10 | 9 | 0.89 | 8.15 |
| Milk | caustic soda | 8 | 8 | 0.9312 | 7.45 |
| Milk | formalin/formaldehyde | 6 | 6 | 0.9417 | 5.65 |
| Milk | salt | 7 | 6 | 0.9286 | 5.55 |
| Milk | glucose | 8 | 6 | 0.9062 | 5.45 |
| Milk | maltodextrin | 5 | 5 | 0.91 | 4.55 |

Leading candidate baseline gaps for this food scope are: Milk -> urea (42 articles, confidence 0.9286); Milk -> ethylene glycol (34 articles, confidence 0.9315); Milk -> detergent (35 articles, confidence 0.9231); Milk -> starch (28 articles, confidence 0.9317); Milk -> formalin/formaldehyde (6 articles, confidence 0.9417); Milk -> palm oil family (12 articles, confidence 0.8812).

![Most reported relationships in the Milk article pool](figures\figure_11_top_milk.png)

*Figure 11. Food is taken from the triplet; the pool only identifies the source collection.*


## 10. Candidate gaps relative to the FSSAI baseline

The gap taxonomy separates exact food-pair coverage from contextual term coverage. Across 1,218 specific news food-candidate combinations, the classes are: candidate not represented in FSSAI baseline: 860, candidate represented, but food-adulterant relation absent: 357, food-adulterant pair represented in FSSAI baseline: 1. A candidate may therefore be present in the FSSAI baseline but absent as an adulterant of the food reported in news. This distinction prevents false conclusions from simple keyword lookup.

| Rank | Food | Candidate | Articles | Mean confidence | FSSAI baseline class | Method class | Score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Ghee | palm oil family | 100 | 0.9117 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 92.8 |
| 2 | Milk | urea | 42 | 0.9286 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 92.79 |
| 3 | Milk | ethylene glycol | 34 | 0.9315 | candidate not represented in FSSAI baseline | method signal occurs in news only | 91.78 |
| 4 | Milk | detergent | 35 | 0.9231 | candidate not represented in FSSAI baseline | method signal occurs in news only | 91.64 |
| 5 | Milk | starch | 28 | 0.9317 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 90.77 |
| 6 | Paneer | starch | 20 | 0.905 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 88.1 |
| 7 | Khoya/mawa | starch | 15 | 0.9029 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 86.56 |
| 8 | Paneer | detergent | 9 | 0.905 | candidate not represented in FSSAI baseline | method signal occurs in news only | 84.1 |
| 9 | Ghee | starch | 11 | 0.8708 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 83.88 |
| 10 | Milk | formalin/formaldehyde | 6 | 0.9417 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 83.46 |
| 11 | Paneer | urea | 6 | 0.9143 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 82.5 |
| 12 | vegetables | pesticide residue | 6 | 0.9111 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 82.38 |
| 13 | fish | formalin/formaldehyde | 5 | 0.93 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 82.21 |
| 14 | Paneer | palm oil family | 14 | 0.9 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 82.11 |
| 15 | fruits | pesticide residue | 6 | 0.9 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 82.0 |
| 16 | ice cream | detergent | 4 | 0.95 | candidate not represented in FSSAI baseline | method signal occurs in news only | 81.93 |
| 17 | everest fish curry masala | ethylene oxide | 3 | 0.95 | candidate not represented in FSSAI baseline | method signal occurs in news only | 80.73 |
| 18 | Milk | palm oil family | 12 | 0.8812 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 80.68 |
| 19 | Sunflower oil | palm oil family | 10 | 0.9 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 80.43 |
| 20 | vegetables | oxytocin | 3 | 0.94 | candidate not represented in FSSAI baseline | no candidate-specific method relation represented | 80.38 |
| 21 | Milk | water | 26 | 0.9176 | candidate represented, but food-adulterant relation absent | candidate-specific method relation represented | 79.89 |
| 22 | Khoya/mawa | detergent | 4 | 0.89 | candidate not represented in FSSAI baseline | method signal occurs in news only | 79.83 |
| 23 | Milk | pesticide residue | 4 | 0.8875 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 79.74 |
| 24 | curry powder masala | ethylene oxide | 2 | 0.95 | candidate not represented in FSSAI baseline | method signal occurs in news only | 79.18 |
| 25 | everest spice mix | ethylene oxide | 2 | 0.95 | candidate not represented in FSSAI baseline | method signal occurs in news only | 79.18 |

![FSSAI baseline representation classes](figures\figure_14_gap_classes.png)

*Figure 14. Absence means absent from the supplied verified baseline, not necessarily from every current FSSAI document.*

![Priority candidates combine recurrence, confidence and local health links](figures\figure_15_gap_priority.png)

*Figure 15. The score is a transparent discovery heuristic, not a risk or prevalence estimate.*

The priority score is a discovery heuristic: 35% mean confidence, 25% log-scaled recurrence, 20% locally represented candidate-effect evidence, 10% absent exact food-pair relation and 10% absent candidate-method relation. It is not a national risk score. A highly ranked result should trigger source inspection and FSSAI-document verification before policy use.

## 11. Test and surveillance priorities

Candidate-method representation classes are: no candidate-specific method relation represented: 822, method signal occurs in news only: 328, candidate-specific method relation represented: 68. Method edges can be missing because the supplied baseline is incomplete, because the ontology lacks a link, because extraction missed it, or because the documents do not specify it. The report therefore proposes a decision workflow rather than asserting a specific laboratory protocol where none is locally represented.

| Rank | Food | Candidate | Articles | Local health basis | Method basis | Recommended action |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Ghee | palm oil family | 100 | harmful for health (1); cardiovascular disease (1); cancer/carcinogenicity (1); health harm (1); increased cholesterol level (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 2 | Milk | urea | 42 | kidney damage (2); organ damage (2); liver damage (2); renal failure (2); stomach irritation (1); multi-organ failure (1); digestive system damage (1); cancer/carcinogenicity (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 3 | Milk | ethylene glycol | 34 | renal failure (31); multi-organ failure (11); anuria (10); vomiting (8); death (6); urinary obstruction (4); gastrointestinal illness (3); nausea (3) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 4 | Milk | detergent | 35 | organ damage (3); gastrointestinal illness (1); stomach irritation (1); vomiting (1); diarrhoea (1); serious health risks (1); gastrointestinal discomfort (1); irritate the digestive tract (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 5 | Milk | starch | 28 | allergic reaction (2); gastrointestinal illness (1); digestive system disturbance (1); stomach pain and loose motions (1); nausea (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 6 | Paneer | starch | 20 | allergic reaction (2); gastrointestinal illness (1); digestive system disturbance (1); stomach pain and loose motions (1); nausea (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 7 | Khoya/mawa | starch | 15 | allergic reaction (2); gastrointestinal illness (1); digestive system disturbance (1); stomach pain and loose motions (1); nausea (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 8 | Paneer | detergent | 9 | organ damage (3); gastrointestinal illness (1); stomach irritation (1); vomiting (1); diarrhoea (1); serious health risks (1); gastrointestinal discomfort (1); irritate the digestive tract (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 9 | Ghee | starch | 11 | allergic reaction (2); gastrointestinal illness (1); digestive system disturbance (1); stomach pain and loose motions (1); nausea (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 10 | Milk | formalin/formaldehyde | 6 | cancer/carcinogenicity (4); gastrointestinal toxicity (1); allergic reaction (1); respiratory problems (1); metabolic disturbances (1); multi-organ failure (1); neurological damage (1); food poisoning (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 11 | Paneer | urea | 6 | kidney damage (2); organ damage (2); liver damage (2); renal failure (2); stomach irritation (1); multi-organ failure (1); digestive system damage (1); cancer/carcinogenicity (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 12 | vegetables | pesticide residue | 6 | cancer/carcinogenicity (8); food poisoning (3); health harms (2); hepatitis (2); cell damage (1); disorders in the biological regulatory systems (1); toxic exposure (1); birth defects (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 13 | fish | formalin/formaldehyde | 5 | cancer/carcinogenicity (4); gastrointestinal toxicity (1); allergic reaction (1); respiratory problems (1); metabolic disturbances (1); multi-organ failure (1); neurological damage (1); food poisoning (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 14 | Paneer | palm oil family | 14 | harmful for health (1); cardiovascular disease (1); cancer/carcinogenicity (1); health harm (1); increased cholesterol level (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 15 | fruits | pesticide residue | 6 | cancer/carcinogenicity (8); food poisoning (3); health harms (2); hepatitis (2); cell damage (1); disorders in the biological regulatory systems (1); toxic exposure (1); birth defects (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 16 | ice cream | detergent | 4 | organ damage (3); gastrointestinal illness (1); stomach irritation (1); vomiting (1); diarrhoea (1); serious health risks (1); gastrointestinal discomfort (1); irritate the digestive tract (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 17 | everest fish curry masala | ethylene oxide | 3 | cancer/carcinogenicity (13); toxicity (2); lymphoma (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 18 | Milk | palm oil family | 12 | harmful for health (1); cardiovascular disease (1); cancer/carcinogenicity (1); health harm (1); increased cholesterol level (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 19 | Sunflower oil | palm oil family | 10 | harmful for health (1); cardiovascular disease (1); cancer/carcinogenicity (1); health harm (1); increased cholesterol level (1) | Candidate-specific method signal occurs in news triplets but not in the FSSAI baseline graph. | Treat the news method as a retrieval lead; verify the full protocol locally before laboratory or enforcement use. |
| 20 | vegetables | oxytocin | 3 | dizziness (2); headaches (2); heart failure (2); infertility (2); health risk to young children (1); side effects on humans (1); cancer/carcinogenicity (1); renal failure (1) | No candidate-specific method relation is represented in either supplied triplet corpus. | Prioritize method discovery and matrix-specific validation; this dataset cannot responsibly name a test. |

![Candidate-specific test representation](figures\figure_16_test_coverage.png)

*Figure 16. A missing graph edge triggers method retrieval and validation; it does not prove no test exists.*

![Most represented news detection and method relations](figures\figure_26_detection_methods.png)

*Figure 26. News-only method language; a method mention is not automatically a validated food-specific protocol.*

For a candidate with an FSSAI baseline method relation, the next step is to retrieve and validate that method for the exact food matrix and enforcement use. For a method mentioned only in news, the article becomes a retrieval lead, not a protocol. Where neither corpus represents a method, the defensible conclusion is a **method-discovery priority**. Minimum validation metadata should include food matrix, analyte identity, sampling, blanks, spikes, recovery, precision, detection and quantification limits, confirmatory rules and chain of custody.

## 12. Health effects and reported impact

The news graph contains 1,229 effect rows. The most represented effects by distinct article are:

| Reported effect | Distinct articles |
| --- | --- |
| cancer/carcinogenicity | 70 |
| fflo acuteeffect | 60 |
| renal failure | 46 |
| death | 38 |
| food poisoning | 35 |
| gastrointestinal illness | 30 |
| vomiting | 27 |
| diarrhoea | 26 |
| cardiovascular disease | 22 |
| anuria | 21 |
| allergic reaction | 20 |
| fflo chroniceffect | 19 |
| acuteeffect | 16 |
| nausea | 14 |
| kidney damage | 13 |
| liver damage | 13 |
| multi-organ failure | 12 |
| obesity | 9 |
| serious health risks | 8 |
| organ damage | 7 |

![Most represented health effects in news triplets](figures\figure_17_health_effects.png)

*Figure 17. These are reported effects in the local corpus, not incidence estimates.*

![Health-effect representation by source food pool](figures\figure_18_effect_food_heatmap.png)

*Figure 18. Pool-level differences reflect corpus composition and repeated coverage.*

These relations describe what the local articles assert. They do not establish clinical incidence, attributable risk or national burden. Effects linked directly from a specific adulterant are stronger graph evidence than an effect connected only to a food, event or generic adulteration statement.

## 13. Causal-chain construction

A food-adulterant-effect chain requires two compatible edges:

1. Food -> `hasAdulterant` -> candidate, or candidate -> `isSubstituteFor` -> food.
2. The same canonical candidate -> an effect relation -> health effect.

Three evidence levels are kept separate. **Direct same-article chains** share a canonical candidate and occur in one article. **Contextual hypotheses** pair a food-adulterant relation with a health effect in the same article without an explicit candidate-effect edge. **Repository-inferred chains** join compatible direct edges from separate sources. Chain confidence is the lower of the mean edge confidences, and support is increased by independent source representation. No chain is called epidemiological proof.

| Food | Adulterant | Effect | Same-article direct chains | FA articles | AE articles | Confidence | Evidence level |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Milk | ethylene glycol | renal failure | 23 | 34 | 24 | 0.9177 | directly joined in the same article |
| Milk | ethylene glycol | multi-organ failure | 10 | 34 | 10 | 0.9315 | directly joined in the same article |
| Milk | ethylene glycol | anuria | 10 | 34 | 10 | 0.885 | directly joined in the same article |
| Milk | unknown adulterant | renal failure | 9 | 33 | 10 | 0.8397 | directly joined in the same article |
| Milk | unknown adulterant | anuria | 7 | 33 | 8 | 0.8397 | directly joined in the same article |
| Milk | ethylene glycol | vomiting | 6 | 34 | 6 | 0.8875 | directly joined in the same article |
| Milk | ethylene glycol | death | 5 | 34 | 5 | 0.8583 | directly joined in the same article |
| Milk | ethylene glycol | urinary obstruction | 4 | 34 | 4 | 0.9 | directly joined in the same article |
| Milk | ethylene glycol | gastrointestinal illness | 3 | 34 | 3 | 0.9167 | directly joined in the same article |
| Milk | unknown adulterant | gastrointestinal illness | 3 | 33 | 3 | 0.8397 | directly joined in the same article |
| Milk | poison | death | 3 | 11 | 5 | 0.86 | directly joined in the same article |
| fruits | pesticide residue | cancer/carcinogenicity | 3 | 6 | 6 | 0.8812 | directly joined in the same article |
| Milk | formalin/formaldehyde | cancer/carcinogenicity | 3 | 6 | 4 | 0.9 | directly joined in the same article |
| everest fish curry masala | ethylene oxide | cancer/carcinogenicity | 3 | 3 | 7 | 0.8885 | directly joined in the same article |
| Milk | unknown contaminant | renal failure | 3 | 4 | 3 | 0.825 | directly joined in the same article |
| Milk | ethylene glycol | dizziness | 2 | 34 | 2 | 0.925 | directly joined in the same article |
| Milk | urea | renal failure | 2 | 42 | 2 | 0.875 | directly joined in the same article |
| Milk | ethylene glycol | nausea | 2 | 34 | 2 | 0.9167 | directly joined in the same article |
| Milk | ethylene glycol | kidney related ailments | 2 | 34 | 2 | 0.9 | directly joined in the same article |
| Milk | urea | organ damage | 2 | 42 | 2 | 0.85 | directly joined in the same article |
| Milk | detergent | organ damage | 2 | 35 | 3 | 0.85 | directly joined in the same article |
| Khoya/mawa | starch | allergic reaction | 2 | 15 | 2 | 0.85 | directly joined in the same article |
| Mustard oil | argemone oil | epidemic dropsy | 2 | 8 | 3 | 0.9333 | directly joined in the same article |
| vegetables | pesticide residue | cancer/carcinogenicity | 2 | 6 | 6 | 0.8812 | directly joined in the same article |
| Milk | refined oil | serious health risk | 2 | 9 | 2 | 0.85 | directly joined in the same article |

![Directly joined food-adulterant-effect chains](figures\figure_19_direct_causal_chains.png)

*Figure 19. Both graph edges occur in the same article and share the canonical adulterant node.*

![Causal-chain evidence levels](figures\figure_20_causal_chain_classes.png)

*Figure 20. Repository-inferred chains are hypotheses and are separated from same-article direct joins.*

![Leading directly joined causal-chain network](figures\figure_29_causal_network.png)

*Figure 29. Blue nodes are foods, gold nodes are adulterants, and red nodes are effects.*

The workbook retains example URLs and both evidence spans for every direct chain. This makes each path auditable and permits human rejection of bad canonical joins.

## 14. Milk, ethylene glycol and renal failure

The local graph directly supports the example raised for this report. Milk -> ethylene glycol appears in 34 distinct news articles; ethylene glycol -> renal failure appears in 24; and 23 articles contain both joinable edges. The conservative chain confidence is 0.9177.

Example food-adulterant evidence: “milk contaminated with ethylene glycol”

Example adulterant-effect evidence: “acute renal failure after consuming milk contaminated with ethylene glycol”

Example source: https://timesofindia.indiatimes.com/city/delhi/whats-cooking-in-pantry-bite-into-adulterated-truth/articleshow/130488415.cms

Repeated articles may cover the same underlying incident. The result establishes strong repository representation of the chain, not 23 independent toxicological confirmations.

## 15. Reverse inference: candidate given food and effect

For a represented food F, effect E and candidate A, the report calculates:

`observed share = articles containing F, E and A / articles containing F and E with at least one food-adulterant relation`

It also reports a binary Laplace-smoothed share `(n + 1) / (N + 2)`. Multiple candidates may occur in one article, so candidate shares need not sum to 100%. This is a retrieval and prioritization score, not the probability that a patient or sample was exposed to the candidate.

| Food | Effect context | Candidate | Context articles | Candidate articles | Observed share | Smoothed share | Mean confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Milk | renal failure | ethylene glycol | 41 | 23 | 56.1% | 55.8% | 0.9413 |
| Milk | multi-organ failure | ethylene glycol | 12 | 11 | 91.7% | 85.7% | 0.95 |
| Milk | anuria | ethylene glycol | 19 | 10 | 52.6% | 52.4% | 0.94 |
| Milk | cancer/carcinogenicity | urea | 21 | 10 | 47.6% | 47.8% | 0.93 |
| Milk | cancer/carcinogenicity | detergent | 21 | 9 | 42.9% | 43.5% | 0.9278 |
| Milk | fflo acuteeffect | ethylene glycol | 29 | 9 | 31.0% | 32.3% | 0.95 |
| Milk | vomiting | ethylene glycol | 16 | 7 | 43.8% | 44.4% | 0.9357 |
| Milk | liver damage | urea | 8 | 5 | 62.5% | 60.0% | 0.93 |
| Milk | food poisoning | water | 10 | 5 | 50.0% | 50.0% | 0.91 |
| Paneer | cancer/carcinogenicity | detergent | 12 | 5 | 41.7% | 42.9% | 0.92 |
| Milk | gastrointestinal illness | urea | 15 | 5 | 33.3% | 35.3% | 0.9 |
| Milk | gastrointestinal illness | detergent | 15 | 5 | 33.3% | 35.3% | 0.89 |
| Milk | death | ethylene glycol | 18 | 5 | 27.8% | 30.0% | 0.93 |
| Milk | cancer/carcinogenicity | starch | 21 | 5 | 23.8% | 26.1% | 0.93 |
| Paneer | kidney damage | detergent | 4 | 4 | 100.0% | 83.3% | 0.925 |
| Milk | urinary obstruction | ethylene glycol | 4 | 4 | 100.0% | 83.3% | 0.95 |
| fruits | cancer/carcinogenicity | pesticide residue | 5 | 4 | 80.0% | 71.4% | 0.9 |
| Ghee | gastrointestinal illness | vanaspati | 6 | 4 | 66.7% | 62.5% | 0.9 |
| Ghee | cardiovascular disease | animal fat | 7 | 4 | 57.1% | 55.6% | 0.9 |
| Milk | kidney damage | urea | 7 | 4 | 57.1% | 55.6% | 0.95 |
| Ghee | cancer/carcinogenicity | vanaspati | 8 | 4 | 50.0% | 50.0% | 0.9125 |
| Milk | liver damage | detergent | 8 | 4 | 50.0% | 50.0% | 0.925 |
| Paneer | food poisoning | starch | 9 | 4 | 44.4% | 45.5% | 0.8625 |
| Paneer | food poisoning | cheese analogue | 9 | 4 | 44.4% | 45.5% | 0.95 |
| Milk | food poisoning | detergent | 10 | 4 | 40.0% | 41.7% | 0.9 |
| Paneer | cancer/carcinogenicity | starch | 12 | 4 | 33.3% | 35.7% | 0.8875 |
| Milk | gastrointestinal illness | water | 15 | 4 | 26.7% | 29.4% | 0.8875 |
| Milk | vomiting | urea | 16 | 4 | 25.0% | 27.8% | 0.925 |
| Milk | vomiting | detergent | 16 | 4 | 25.0% | 27.8% | 0.925 |
| Ghee | food poisoning | vanaspati | 3 | 3 | 100.0% | 80.0% | 0.9 |

![Candidate presence given Milk and renal-failure context](figures\figure_21_renal_reverse_hypothesis.png)

*Figure 21. The percentage is an article association share, not a diagnostic or causal probability.*

For Milk and renal failure, ethylene glycol is named in 23/41 represented articles (56.1%). This is substantially more represented than urea or detergent in the same context. The correct operational use is to prioritize ethylene-glycol evidence retrieval and testing consideration while keeping alternatives open.

## 16. Food specificity

Food specificity asks whether a candidate's direct food-link articles concentrate in one matrix. It is based on explicitly extracted food-candidate relations, not the article pool label. This matters because an effect associated with a candidate in Milk should not automatically imply equal relevance in Oil or Ghee.

![Food specificity of leading adulterant candidates](figures\figure_22_food_specificity.png)

*Figure 22. This directly answers whether a candidate is represented across foods or concentrated in one food matrix.*

For ethylene glycol, the represented distribution is: Milk: 34 articles (81.0%), cough syrup: 2 articles (4.8%), Curd/yoghurt: 1 articles (2.4%), syrup: 1 articles (2.4%), propylene glycol: 1 articles (2.4%), pharmaceutical grade propylene glycol: 1 articles (2.4%), medicinal syrups: 1 articles (2.4%), dok 1 max syrup: 1 articles (2.4%). Small denominators and generic food labels remain visible in the workbook.

## 17. Time series

Time-series tables use publication year. They count unique articles with direct food-adulterant relations and are not adjusted for crawler intensity, duplicate reporting or partial-year coverage. They are appropriate for corpus monitoring and emergence detection, not prevalence estimation.

![Publication-year coverage by food pool](figures\figure_23_time_food_pool.png)

*Figure 23. Publication date is not incident date; 2026 is partial and collection intensity varies.*

![Publication trajectories of leading candidates](figures\figure_24_candidate_time_series.png)

*Figure 24. Trends describe the collected corpus and repeated reporting, not population prevalence.*

## 18. Regulatory actions and response intelligence

News adds actions, bodies, targets, operators and incident findings that are sparse in standards-oriented text. These relations are relevant to an operational food-safety graph even when they do not change the food chemistry.

![Most represented regulatory-action relations](figures\figure_25_regulatory_actions.png)

*Figure 25. Action relations complement food chemistry by showing what authorities or operators did.*

The action table in the workbook preserves subject, predicate, object, source count, confidence and example evidence. Repeated action reports should be clustered by incident before counting enforcement events.

## 19. Source concentration and duplication

The analysis uses unique articles rather than rows for recurrence, but syndicated and follow-up coverage can still describe one event. Publisher concentration and known title clusters show why article frequency cannot be read as incident frequency.

![News-source concentration](figures\figure_27_publisher_concentration.png)

*Figure 27. Concentrated sourcing can amplify repeated incidents and editorial framing.*

The causal and reverse-inference results should ultimately be repeated after event-level deduplication. Until then, article count measures the strength of corpus representation, not independent-event count.

## 20. Interpreting “FSSAI gaps”

Four different phenomena can produce a missing edge:

1. **Document coverage candidate:** the supplied baseline does not contain the concept or relation.
2. **Extraction gap:** a source document may contain it, but the verified triplet file does not.
3. **Terminology gap:** baseline and news use different labels for the same entity.
4. **Ontology gap:** both concepts exist, but the relation needed to connect food, candidate, method, effect or action is absent.

The report can discover and rank these cases, but only source-document inspection distinguishes them. Accordingly, all gap labels say “not represented in the FSSAI baseline.”

## 21. AI-for-social-good research design

A defensible system should retain seven connected layers: immutable source text; atomic triplets with evidence and confidence; conservative entity resolution; article and incident deduplication; causal-path construction with evidence levels; FSSAI baseline alignment; and human/laboratory verification queues. The output is a decision-support graph, not an autonomous regulatory conclusion.

The key evaluation units are food-candidate pair precision, candidate-effect edge precision, entity-link precision, article-to-event cluster precision, method-link completeness, evidence-span exactness and calibration of confidence against human review. Reverse hypotheses should be evaluated as retrieval rankings using held-out, event-deduplicated cases.

## 22. Limitations

- News coverage is selective, duplicated and editorially mediated.
- Article count is not incident count; incident count is not prevalence.
- Confidence is model-supplied and not demonstrated to be calibrated.
- Blank subject/object identifiers force lexical canonicalization.
- Alias normalization can create false joins; raw surfaces and evidence are retained for review.
- Same-article context is not a causal assertion.
- Repository-inferred chains join claims across sources and are hypotheses only.
- Publication date is not incident date.
- The FSSAI baseline is a supplied verified extract, not a guaranteed exhaustive representation of every current FSSAI document.
- No external toxicology or analytical-method source is used; health and method conclusions are bounded by local graph content.

## 23. Conclusions

The combined graph is most useful as a structured gap-discovery and hypothesis-routing system. News contributes food-specific adulterants, effects, detection leads, actions and event context that the FSSAI baseline often does not connect. The strongest locally represented causal pattern is Milk -> ethylene glycol -> renal failure, and food-specificity analysis shows why that evidence should not be transferred indiscriminately to Oil or Ghee.

The practical next step is not automatic ontology expansion. It is a ranked verification program: inspect the source article and FSSAI documents; validate entity identity and food role; deduplicate incidents; retrieve or develop a matrix-appropriate method; and record the resulting accepted, rejected or newly modeled edge. The package supplies all rows, evidence, confidence, rankings and figure data required for that process.

## Appendix A. Top 25 candidate gaps

| Rank | Food | Candidate | Articles | Mean confidence | FSSAI baseline class | Method class | Score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Ghee | palm oil family | 100 | 0.9117 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 92.8 |
| 2 | Milk | urea | 42 | 0.9286 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 92.79 |
| 3 | Milk | ethylene glycol | 34 | 0.9315 | candidate not represented in FSSAI baseline | method signal occurs in news only | 91.78 |
| 4 | Milk | detergent | 35 | 0.9231 | candidate not represented in FSSAI baseline | method signal occurs in news only | 91.64 |
| 5 | Milk | starch | 28 | 0.9317 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 90.77 |
| 6 | Paneer | starch | 20 | 0.905 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 88.1 |
| 7 | Khoya/mawa | starch | 15 | 0.9029 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 86.56 |
| 8 | Paneer | detergent | 9 | 0.905 | candidate not represented in FSSAI baseline | method signal occurs in news only | 84.1 |
| 9 | Ghee | starch | 11 | 0.8708 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 83.88 |
| 10 | Milk | formalin/formaldehyde | 6 | 0.9417 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 83.46 |
| 11 | Paneer | urea | 6 | 0.9143 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 82.5 |
| 12 | vegetables | pesticide residue | 6 | 0.9111 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 82.38 |
| 13 | fish | formalin/formaldehyde | 5 | 0.93 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 82.21 |
| 14 | Paneer | palm oil family | 14 | 0.9 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 82.11 |
| 15 | fruits | pesticide residue | 6 | 0.9 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 82.0 |
| 16 | ice cream | detergent | 4 | 0.95 | candidate not represented in FSSAI baseline | method signal occurs in news only | 81.93 |
| 17 | everest fish curry masala | ethylene oxide | 3 | 0.95 | candidate not represented in FSSAI baseline | method signal occurs in news only | 80.73 |
| 18 | Milk | palm oil family | 12 | 0.8812 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 80.68 |
| 19 | Sunflower oil | palm oil family | 10 | 0.9 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 80.43 |
| 20 | vegetables | oxytocin | 3 | 0.94 | candidate not represented in FSSAI baseline | no candidate-specific method relation represented | 80.38 |
| 21 | Milk | water | 26 | 0.9176 | candidate represented, but food-adulterant relation absent | candidate-specific method relation represented | 79.89 |
| 22 | Khoya/mawa | detergent | 4 | 0.89 | candidate not represented in FSSAI baseline | method signal occurs in news only | 79.83 |
| 23 | Milk | pesticide residue | 4 | 0.8875 | candidate represented, but food-adulterant relation absent | method signal occurs in news only | 79.74 |
| 24 | curry powder masala | ethylene oxide | 2 | 0.95 | candidate not represented in FSSAI baseline | method signal occurs in news only | 79.18 |
| 25 | everest spice mix | ethylene oxide | 2 | 0.95 | candidate not represented in FSSAI baseline | method signal occurs in news only | 79.18 |

## Appendix B. Top 25 direct causal chains

| Food | Adulterant | Effect | Same-article direct chains | FA articles | AE articles | Confidence | Evidence level |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Milk | ethylene glycol | renal failure | 23 | 34 | 24 | 0.9177 | directly joined in the same article |
| Milk | ethylene glycol | multi-organ failure | 10 | 34 | 10 | 0.9315 | directly joined in the same article |
| Milk | ethylene glycol | anuria | 10 | 34 | 10 | 0.885 | directly joined in the same article |
| Milk | unknown adulterant | renal failure | 9 | 33 | 10 | 0.8397 | directly joined in the same article |
| Milk | unknown adulterant | anuria | 7 | 33 | 8 | 0.8397 | directly joined in the same article |
| Milk | ethylene glycol | vomiting | 6 | 34 | 6 | 0.8875 | directly joined in the same article |
| Milk | ethylene glycol | death | 5 | 34 | 5 | 0.8583 | directly joined in the same article |
| Milk | ethylene glycol | urinary obstruction | 4 | 34 | 4 | 0.9 | directly joined in the same article |
| Milk | ethylene glycol | gastrointestinal illness | 3 | 34 | 3 | 0.9167 | directly joined in the same article |
| Milk | unknown adulterant | gastrointestinal illness | 3 | 33 | 3 | 0.8397 | directly joined in the same article |
| Milk | poison | death | 3 | 11 | 5 | 0.86 | directly joined in the same article |
| fruits | pesticide residue | cancer/carcinogenicity | 3 | 6 | 6 | 0.8812 | directly joined in the same article |
| Milk | formalin/formaldehyde | cancer/carcinogenicity | 3 | 6 | 4 | 0.9 | directly joined in the same article |
| everest fish curry masala | ethylene oxide | cancer/carcinogenicity | 3 | 3 | 7 | 0.8885 | directly joined in the same article |
| Milk | unknown contaminant | renal failure | 3 | 4 | 3 | 0.825 | directly joined in the same article |
| Milk | ethylene glycol | dizziness | 2 | 34 | 2 | 0.925 | directly joined in the same article |
| Milk | urea | renal failure | 2 | 42 | 2 | 0.875 | directly joined in the same article |
| Milk | ethylene glycol | nausea | 2 | 34 | 2 | 0.9167 | directly joined in the same article |
| Milk | ethylene glycol | kidney related ailments | 2 | 34 | 2 | 0.9 | directly joined in the same article |
| Milk | urea | organ damage | 2 | 42 | 2 | 0.85 | directly joined in the same article |
| Milk | detergent | organ damage | 2 | 35 | 3 | 0.85 | directly joined in the same article |
| Khoya/mawa | starch | allergic reaction | 2 | 15 | 2 | 0.85 | directly joined in the same article |
| Mustard oil | argemone oil | epidemic dropsy | 2 | 8 | 3 | 0.9333 | directly joined in the same article |
| vegetables | pesticide residue | cancer/carcinogenicity | 2 | 6 | 6 | 0.8812 | directly joined in the same article |
| Milk | refined oil | serious health risk | 2 | 9 | 2 | 0.85 | directly joined in the same article |

## Appendix C. Reverse hypotheses with at least three context articles

| Food | Effect context | Candidate | Context articles | Candidate articles | Observed share | Smoothed share | Mean confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Milk | renal failure | ethylene glycol | 41 | 23 | 56.1% | 55.8% | 0.9413 |
| Milk | multi-organ failure | ethylene glycol | 12 | 11 | 91.7% | 85.7% | 0.95 |
| Milk | anuria | ethylene glycol | 19 | 10 | 52.6% | 52.4% | 0.94 |
| Milk | cancer/carcinogenicity | urea | 21 | 10 | 47.6% | 47.8% | 0.93 |
| Milk | cancer/carcinogenicity | detergent | 21 | 9 | 42.9% | 43.5% | 0.9278 |
| Milk | fflo acuteeffect | ethylene glycol | 29 | 9 | 31.0% | 32.3% | 0.95 |
| Milk | vomiting | ethylene glycol | 16 | 7 | 43.8% | 44.4% | 0.9357 |
| Milk | liver damage | urea | 8 | 5 | 62.5% | 60.0% | 0.93 |
| Milk | food poisoning | water | 10 | 5 | 50.0% | 50.0% | 0.91 |
| Paneer | cancer/carcinogenicity | detergent | 12 | 5 | 41.7% | 42.9% | 0.92 |
| Milk | gastrointestinal illness | urea | 15 | 5 | 33.3% | 35.3% | 0.9 |
| Milk | gastrointestinal illness | detergent | 15 | 5 | 33.3% | 35.3% | 0.89 |
| Milk | death | ethylene glycol | 18 | 5 | 27.8% | 30.0% | 0.93 |
| Milk | cancer/carcinogenicity | starch | 21 | 5 | 23.8% | 26.1% | 0.93 |
| Paneer | kidney damage | detergent | 4 | 4 | 100.0% | 83.3% | 0.925 |
| Milk | urinary obstruction | ethylene glycol | 4 | 4 | 100.0% | 83.3% | 0.95 |
| fruits | cancer/carcinogenicity | pesticide residue | 5 | 4 | 80.0% | 71.4% | 0.9 |
| Ghee | gastrointestinal illness | vanaspati | 6 | 4 | 66.7% | 62.5% | 0.9 |
| Ghee | cardiovascular disease | animal fat | 7 | 4 | 57.1% | 55.6% | 0.9 |
| Milk | kidney damage | urea | 7 | 4 | 57.1% | 55.6% | 0.95 |
| Ghee | cancer/carcinogenicity | vanaspati | 8 | 4 | 50.0% | 50.0% | 0.9125 |
| Milk | liver damage | detergent | 8 | 4 | 50.0% | 50.0% | 0.925 |
| Paneer | food poisoning | starch | 9 | 4 | 44.4% | 45.5% | 0.8625 |
| Paneer | food poisoning | cheese analogue | 9 | 4 | 44.4% | 45.5% | 0.95 |
| Milk | food poisoning | detergent | 10 | 4 | 40.0% | 41.7% | 0.9 |
| Paneer | cancer/carcinogenicity | starch | 12 | 4 | 33.3% | 35.7% | 0.8875 |
| Milk | gastrointestinal illness | water | 15 | 4 | 26.7% | 29.4% | 0.8875 |
| Milk | vomiting | urea | 16 | 4 | 25.0% | 27.8% | 0.925 |
| Milk | vomiting | detergent | 16 | 4 | 25.0% | 27.8% | 0.925 |
| Ghee | food poisoning | vanaspati | 3 | 3 | 100.0% | 80.0% | 0.9 |

## Appendix D. Reproducibility

Inputs are `triplets_verified.csv`, `News_Triplets_Oil_Ghee_Milk_20260820.csv`, and the three local article JSONL files listed in `package_manifest.json`. Run `python build_triplet_intelligence_report.py` from the repository root. Every output has a SHA-256 digest in the package manifest. No network call is made by the builder.
