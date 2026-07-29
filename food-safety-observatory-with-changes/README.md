# Indian Food Safety Incident Observatory

A production-oriented research website for the Food Computing Lab at Ashoka University. The application makes the current edible-oil and ghee news corpora searchable and auditable, documents the classification pipeline, and is ready to accept validated event extraction, ontology and FSSAI comparison records.

The interface does not independently verify claims in news reports. Human labels, trained-classifier predictions and future large-model validation outputs are represented as separate fields.

## Current Data Snapshot

`data/articles.csv` is generated from project outputs by `scripts/import_project_data.py`.

- 1,558 article records
- 503 edible-oil records
- 1,055 ghee records
- 691 human-reviewed records
- 274 human-labelled relevant records
- 417 human-labelled irrelevant records
- 867 ghee records pending human review
- 514 records with trained-classifier predictions
- No local relevance-LLM labels or scores included
- Future large-model event-validator fields intentionally blank

The ghee classifier scores currently available are unchanged transfer-test outputs from the edible-oil ensemble. They are explicitly identified as out-of-domain results, not a final ghee classifier.

## Technology

- Next.js 16 with TypeScript and the App Router
- React 19
- Tailwind CSS 4
- Recharts
- Leaflet and React Leaflet
- Radix UI primitives and shadcn-style local components
- Lucide icons
- Papa Parse
- Python, pandas and openpyxl for data preparation

## Install and Run

```powershell
cd food-safety-observatory
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Production verification:

```powershell
npm run lint
npm run build
npm run start
```

## Routes

- `/` overview, metrics, coverage and research pipeline
- `/incidents` searchable repository with filters, sorting, pagination and grid/list views
- `/incidents/[slug]` article metadata, classifier output, extraction fields and cleaned text
- `/timeline` data-generated publication and label charts
- `/geography` Leaflet map with a validated-location availability state
- `/taxonomy` provisional food and issue taxonomy explorer
- `/fssai-baseline` milk and edible-oil survey scope plus comparison framework
- `/methodology` pipeline documentation and edible-oil ensemble results
- `/about` project context and team placeholders

## Data Files

| File | Purpose |
| --- | --- |
| `data/articles.csv` | Active website corpus |
| `data/articles.sample.csv` | Clearly labelled interface-only demonstration records |
| `data/current-data-report.json` | Summary of the generated project export |
| `data/fssai-baselines.json` | Survey scope and tested dimensions; no unsupplied numerical findings |
| `data/taxonomy.json` | Replaceable provisional taxonomy |

To test the demo banner, temporarily replace `data/articles.csv` with `data/articles.sample.csv`. Every sample row has `is_demo: true` and is labelled as fictional interface-test data.

## Article Schema

The resilient loader accepts missing optional columns. Blank strings, `NaN`, `null`, `None`, `N/A` and `undefined` are treated as missing.

```text
article_id
title
source
date
url
raw_text
cleaned_text
food_keyword
human_label
label_source
review_status
classifier_label
classifier_score
classifier_model
llm_event_present
llm_validator_label
llm_confidence
food_item
adulterant_or_issue
location_city
location_district
location_state
latitude
longitude
quantity
authority_or_evidence
action_taken
date_of_incident
quadrant
ontology_id
ontology_category
evidence_excerpt
notes
round_number
is_demo
```

The requested base schema is supported, with `human_label`, `label_source`, `review_status`, `round_number` and `is_demo` added to preserve research provenance.

Labels are normalised from values such as `1/0`, `relevant/irrelevant`, `keep/drop`, `yes/no` and `true/false`. Dates and numeric scores are parsed defensively. A missing `article_id` receives a deterministic hash for loading, while the preparation utility writes stable identifiers into the export.

## Prepare an External CSV or Excel File

Install the Python data dependencies:

```powershell
python -m pip install -r scripts/requirements.txt
```

Run:

```powershell
python scripts/prepare_data.py path\to\input.xlsx `
  --output-csv data\articles.csv `
  --output-json data\articles.json `
  --report data\data-quality-report.json
```

The utility:

- accepts `.csv`, `.xlsx` and `.xls` input;
- standardises column names and common aliases;
- validates required `title` and `url` columns;
- generates missing stable article IDs;
- removes duplicate article IDs from the export;
- flags duplicate URLs without silently removing them;
- reports missingness for every extraction field;
- preserves text through structured CSV/JSON writers; and
- never writes to or modifies the original input file.

## Rebuild from This Repository's Research Outputs

From the application directory:

```powershell
python scripts/import_project_data.py
```

This merges the current edible-oil master corpus, out-of-fold predictions from the winning ensemble, the ghee article corpus, human ghee review marks and the documented classifier transfer-test predictions. It deliberately discards the local relevance-LLM columns from the source ghee file.

## Add Ontology Data

Replace `data/taxonomy.json` while preserving the `TaxonomyData` structure in `lib/types.ts`:

```json
{
  "status": "validated",
  "food_categories": [],
  "issue_categories": []
}
```

Nodes support `id`, `name`, `definition`, `parent_id`, `children` and `fssai_relationship`. Populate article-level `ontology_id` and `ontology_category` fields to connect incident records to validated nodes.

## Add FSSAI Baseline Records

Append records to `data/fssai-baselines.json` using the `FssaiBaseline` type. Keep survey scope, tested dimensions and numerical findings distinct. Do not add a statistic unless its source, unit, sample and interpretation have been validated.

Future article-to-survey comparison records should distinguish:

- **Alignment**: a news issue matches an explicitly tested parameter;
- **Divergence**: comparable evidence appears to show different patterns; and
- **Scope Gap**: the news issue was not tested or explicitly covered.

## Deploy to Vercel

1. Push the repository to GitHub.
2. Import the repository in Vercel.
3. Set the project root to `food-safety-observatory`.
4. Use the default Next.js framework preset.
5. Build with `npm run build`.
6. Deploy.

The active CSV is read on the server. For larger Phase 2 corpora, move article text into a database or object store and retain a local metadata export for reproducible releases.

## Current Limitations

- News discovery and crawling do not guarantee complete coverage.
- 867 ghee records remain pending human review in the current workbook.
- The edible-oil classifier transfer test is not a final ghee classifier.
- Large-model event validation has not yet populated the website dataset.
- Event entities, evidence spans, ontology mappings and geographic fields are not yet available.
- FSSAI numerical findings and article-to-survey comparisons are not loaded.
- The Leaflet base map uses free OpenStreetMap tiles and requires network access to render map imagery.
- The CSV adapter is appropriate for the current corpus size, not an unlimited production archive.

## Phase 2 Integration Plan

1. Complete the ghee human-review queue and train or calibrate a ghee-specific classifier.
2. Run the planned larger-model event validator on classifier outputs.
3. Extract food item, adulterant or issue, location, quantity, authority, action and incident date.
4. Manually validate extraction fields and evidence spans.
5. Populate TP/FP/TN/FN quadrants against the validated event labels.
6. Replace the provisional taxonomy with validated Indian food ontology data.
7. Load FSSAI report parameters and source-linked numerical results.
8. Generate alignment, divergence and scope-gap comparison records.
9. Move full text to a queryable data service when the corpus exceeds the practical CSV/RSC payload size.

## Research Disclaimer

Classification and extraction outputs are research annotations. They should not be treated as independent verification of the claims contained in the original news report.
