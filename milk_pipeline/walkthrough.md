# Pipeline Implementation Completed

I have implemented the full iterative milk adulteration pipeline based on your feedback. The pipeline is now configured to use **KeyBERT** for keyword extraction, **Media Cloud** for article fetching, and includes an interactive **manual sorting pause** for your review step.

Here is a walkthrough of what was changed and how to run your pipeline.

## 1. Extracting the Seeds

The `milk_sample_articles.docx` file you provided contains a list of 20 URLs. Since KeyBERT needs actual text (not just URLs) to extract keywords, I created a utility script to fetch and scrape the full text from those URLs.

**What was added:**
- [parse_seeds.py](file:///c:/Myself/milk_pipeline/parse_seeds.py): A script that uses `python-docx` to extract the links, and `trafilatura` to scrape their content into `seeds/seed_articles.json`.

## 2. Iterative Pipeline Implementation

All the core stubs in the `pipeline/` directory have been filled out:

- **Keyword Extraction:** [pipeline/extract_keywords.py](file:///c:/Myself/milk_pipeline/pipeline/extract_keywords.py) now uses `KeyBERT` to extract keywords (unigrams to trigrams). It averages the term scores across all articles in the round and selects the top-scoring keywords.
- **Query Building:** [pipeline/build_query.py](file:///c:/Myself/milk_pipeline/pipeline/build_query.py) builds a Solr-compliant `OR` query, safely wrapping multi-word terms in quotes.
- **Media Cloud Fetching:** [pipeline/fetch_articles.py](file:///c:/Myself/milk_pipeline/pipeline/fetch_articles.py) interacts directly with the Media Cloud Search API (`https://search.mediacloud.org/api/search`). It includes exponential backoff for resilience.
- **Relevance Scoring:** [pipeline/filter_relevance.py](file:///c:/Myself/milk_pipeline/pipeline/filter_relevance.py) includes a blocklist filter for boilerplate text and an automated scoring function that counts keyword matches in the article body.
- **Full-Text Scraping & Dedup:** Added [pipeline/scrape_fulltext.py](file:///c:/Myself/milk_pipeline/pipeline/scrape_fulltext.py) to fetch the final survived articles and [pipeline/dedup.py](file:///c:/Myself/milk_pipeline/pipeline/dedup.py) to remove overlaps.

## 3. Manual Filtering Workflow

In [run_pipeline.py](file:///c:/Myself/milk_pipeline/run_pipeline.py), I have added an explicit date constraint for `2021-01-01` and an **interactive pause state**. 

At the end of every round, the pipeline will halt in your terminal:
```text
==================================================
*** MANUAL FILTERING PAUSE ***
Please review data\round_X_filtered\filtered_results.json and manually remove any irrelevant articles.
Press Enter when you are done to continue to the next step...
```
You can simply open `filtered_results.json` in your IDE, delete the JSON blocks of the articles you don't want to keep, save the file, and press `Enter` in the terminal to resume the pipeline with only your curated articles.

---

## How to Run the Pipeline

1. **Set your API Token:** Open a terminal in `c:\Myself\milk_pipeline` and set your Media Cloud token as an environment variable:
   ```powershell
   $env:MC_API_TOKEN="your_media_cloud_api_token"
   ```
2. **Generate the Seed File:** Run the seed parser to download the text for your 20 seed articles. (Wait for this to complete before running step 3).
   ```powershell
   python parse_seeds.py
   ```
3. **Start the Pipeline:** 
   ```powershell
   python run_pipeline.py
   ```
