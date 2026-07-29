"""
Filter round_1_filtered/filtered_results.json to keep only articles
directly related to milk adulteration or low-quality milk cases.
"""
import json

FILTERED_PATH = r"c:\Users\Writika\milk_pipeline\data\round_1_filtered\filtered_results.json"

# URLs (or URL fragments) that are clearly off-topic
REMOVE_URL_FRAGMENTS = [
    # Milk pricing / Flipkart controversy
    "flipkart-may-be-facing-problem",
    # Bihar liquor smuggled in milk cans — tangentially related but not food safety
    "pure-milk-protein-shakes-how-dry-bihar",
    # Religious ritual — milk poured in river
    "11000-litres-of-milk-poured-into-narmada",
    # Generic political statement (CM Naidu on social equity)
    "social-equity-is-nda-govts-policy",
    "social-equity-is-nda-govt-s-policy",
    # School news roundup
    "today-news-headlines-for-school-assembly",
    # KMF RTI ruling — not adulteration
    "karnataka-milk-federation-a-state-body-fully-under-rti",
    # Cyclone disaster news
    "cyclone-montha",
    # Man using milk can lid as helmet
    "milk-can-lid-as-helmet",
    # Lifestyle / diet tips
    "7-food-items-you-should-avoid-consuming-with-milk",
    "dnaindia.com/lifestyle",
    "dnaindia.com/viral",
    # Celebrity lifestyle
    "sara-ali-khan-revealed-her-morning-routine",
    "ambani-s-drinks-milk-only-from-this-dairy-cattle-breed",
    # Brand awareness marketing
    "sids-farm-launches-awareness-campaign-on-pure-milk",
    # Flood relief food distribution
    "ntr-dist-gets-50k-food-packets-milk-from-eluru",
    # General dairy sector opinion piece
    "success-of-india-s-dairy-sector-is-not-just-thanks-to-private-players",
    "milk-production-india-dairy-sector-farmers-milk-price",
    # Housing quality in Kakinada (completely unrelated)
    "kakinada-maintain-quality-in-housing-works",
    # AP pension news
    "senior-citizens-in-andhra-pradesh-overjoyed-as-govt-raises-pension",
    # Breast milk sale
    "sale-of-breast-milk-raises-eyebrows",
    # Buffalo milk yield record
    "murrah-buffalo-yields-27-42-kg-milk-sets-record",
]

with open(FILTERED_PATH, "r", encoding="utf-8") as f:
    articles = json.load(f)

before = len(articles)
kept = []
removed = []

for a in articles:
    url = a.get("url", "").lower()
    if any(fragment.lower() in url for fragment in REMOVE_URL_FRAGMENTS):
        removed.append(a["title"] or a["url"])
    else:
        kept.append(a)

with open(FILTERED_PATH, "w", encoding="utf-8") as f:
    json.dump(kept, f, indent=2, ensure_ascii=False)

print(f"Before: {before} articles")
print(f"After:  {len(kept)} articles")
print(f"Removed ({len(removed)}):")
for t in removed:
    print(f"  - {t[:100]}")
