"""
Central configuration for the milk adulteration news pipeline.

Keep every tunable constant here, not buried inside individual modules.
When you're debugging "why did round 2 behave differently from round 1",
this file should be the first place you check.
"""

from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
SEEDS_DIR = BASE_DIR / "seeds"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

# ── Pipeline control ─────────────────────────────────────────────────
NUM_ROUNDS = 10              # how many keyword-expansion iterations to run
MAX_QUERY_TERMS = 20         # hard cap on keywords per Solr query (timeout prevention)
MAX_RESULTS_PER_QUERY = 1000 # cap per API call — keep requests cheap and fast

# ── Relevance filter (precision-biased — see filter_relevance.py) ────
MIN_KEYWORD_MATCHES_ROUND1 = 2   # article body must contain >=2 seed keywords to count
MIN_KEYWORD_MATCHES_LATER_ROUNDS = 2  # only relax this deliberately, and log when you do

# ── Keyword filter ────────────────────────────────────────────────────
TOP_N_KEYWORDS_PER_ROUND = 6     # max keywords kept after manual/automated filtering

# Manually maintained — add terms here as you discover boilerplate junk
# coming out of KeyBERT (e.g. wire-service boilerplate, generic attribution
# phrases). This list grows as you actually look at your data.
KEYWORD_BLOCKLIST = {

    # Milk pricing & market dynamics (not adulteration)
    "marketed",
    "price",
    "prices",
    "predatory",
    "flipkart",
    "quick commerce",
    "re 1",
    "registration",
    "registered",
    "unregistered",
    "cheap",
    "today news headlines",
    "ghee supplied",
    "ghee adulteration",
    "sewage",
    "milk can lid",
    # Dairy cooperative / brand business news (KMF, BAMUL, Nandini, Amul etc.)
    "federation",
    "kmf",
    "bamul",
    "nandini",
    "amul",
    "mother dairy",
    "cooperative",
    "pregnancy",
    "breast milk",
    "breastfeeding",
    "infant",
    "ghee",
    "record",
    "yields",

    # Sports sponsorships that surface because Nandini sponsors RCB
    "ipl",
    "rcb",
    "cricket",
    "lifestyle",
    "diet",

    # Generic terms that pull in unrelated crackdowns
    "drug imports",
    "predatory pricing",
    "expired",
    "inmate",
    "jails",
    "toddy",
    "helmet",
    "petrol pump",
    "yields",
    "awareness drive",
    "awareness campaign",
    "IIT",
    "karur",
    "chocolate",
    "paneer",
    "milk powder",
    "eluru",
    "adulterated mawa",
    "narmada",
    "adulterated paneer",
    "gutka",

}

# ── API ───────────────────────────────────────────────────────────────
REQUEST_TIMEOUT_SECONDS = 180  # Media Cloud Solr queries can be slow; 60s is safer
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2  # doubles each retry: 2s, 4s, 8s

# ── Media Cloud collection IDs ────────────────────────────────────────
# Discovered via: https://search.mediacloud.org/api/sources/collections/?name=India&platform=onlinenews-mediacloud
# 34412118 = "India - National" (featured, monitored)
# 38379954 = "India - State & Local" (monitored — covers regional press)
MC_COLLECTION_IDS = [34412118, 38379954]
