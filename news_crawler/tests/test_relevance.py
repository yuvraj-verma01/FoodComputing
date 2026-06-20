"""Tests for the relevance scorer.

Uses the 12 seed article snippets as ground-truth examples.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.config import Config
from crawler.relevance import RelevanceScorer, url_looks_relevant


@pytest.fixture
def cfg():
    return Config()


@pytest.fixture
def scorer(cfg):
    return RelevanceScorer(cfg)


# Ground-truth positive examples derived from oil_sample_articles.docx
POSITIVE_EXAMPLES = [
    {
        "title": "Major crackdown on adulterated ghee and oil in Pokaran: over 14000kg seized",
        "text": "Food safety officers in Rajasthan seized over 14,000 kg of adulterated ghee "
                "and edible oil from a warehouse in Pokaran during a surprise raid. "
                "The FSSAI-led team found mustard oil mixed with cheaper palm oil.",
        "url": "https://timesofindia.indiatimes.com/city/jaipur/major-crackdown/articleshow/131486941.cms",
        "date": "2025-01-15",
    },
    {
        "title": "6000 litres of fake mustard oil seized in UP Barabanki raises food safety concerns",
        "text": "Police and food safety officials in Barabanki, Uttar Pradesh, seized "
                "approximately 6,000 litres of fake mustard oil from an illegal godown. "
                "Samples sent to FSSAI lab for testing.",
        "url": "https://www.news18.com/india/up-barabanki-6000-litres-of-fake-mustard-oil",
        "date": "2024-03-10",
    },
    {
        "title": "Over 4 lakh litres seized in drive against substandard edible oil in UP",
        "text": "The Uttar Pradesh food safety department conducted a state-wide drive "
                "and seized over four lakh litres of substandard edible oil. "
                "Multiple FIRs registered and manufacturers arrested.",
        "url": "https://theprint.in/india/over-4-lakh-litres-seized/2866887/",
        "date": "2024-05-20",
    },
    {
        "title": "FSSAI seizes 14000 litres of adulterated oil ahead of festive season",
        "text": "FSSAI conducted raids across Kanpur and seized 14,000 litres of adulterated "
                "cooking oil, 1,320 kg of rotten dates. The oil was found to be mixed with "
                "mineral oil, a health hazard.",
        "url": "https://www.healthandme.com/nutrition/kanpur-food-adulteration-fssai",
        "date": "2024-09-05",
    },
    {
        "title": "17k litres of adulterated coconut oil seized in Thiruvananthapuram",
        "text": "Kerala food safety officials seized 17,000 litres of adulterated coconut oil "
                "from a processing unit in Thiruvananthapuram. The oil was found mixed with "
                "cheaper palm oil and was being sold under a popular brand name.",
        "url": "https://www.newindianexpress.com/cities/thiruvananthapuram/17k-litres-adulterated",
        "date": "2025-08-20",
    },
]

# Ground-truth negative examples (should be irrelevant or maybe)
NEGATIVE_EXAMPLES = [
    {
        "title": "Best cooking oil brands in India: A buyer's guide",
        "text": "Looking to buy the best cooking oil? Here are our top picks for "
                "healthy cooking oils available in India: sunflower oil, mustard oil, "
                "and coconut oil. Compare prices per litre and buy online.",
        "url": "https://example.com/buy-cooking-oil",
        "date": "2024-01-01",
    },
    {
        "title": "Edible oil prices surge on MCX as global commodity market tightens",
        "text": "Edible oil futures on MCX surged 3% today as global soybean supply "
                "tightened. Palm oil futures on NCDEX also rose. Analysts expect "
                "prices to remain elevated in the coming weeks.",
        "url": "https://example.com/oil-market-price",
        "date": "2024-01-01",
    },
    {
        "title": "How to check purity of mustard oil at home",
        "text": "Here's a simple guide on how to check the purity of mustard oil "
                "at home using a refrigerator test. Pure mustard oil will solidify "
                "when cooled, while adulterated oil remains liquid.",
        "url": "https://example.com/how-to-check-purity",
        "date": "2024-01-01",
    },
]


class TestPositiveExamples:
    def test_seed_articles_score_relevant(self, scorer):
        for ex in POSITIVE_EXAMPLES:
            result = scorer.score(
                text=ex["text"],
                title=ex["title"],
                url=ex["url"],
                publication_date=ex["date"],
            )
            assert result.label in ("relevant", "maybe_relevant"), (
                f"Expected relevant/maybe for '{ex['title']}' but got "
                f"{result.label} (score={result.score})"
            )

    def test_positive_scores_above_threshold(self, scorer):
        for ex in POSITIVE_EXAMPLES:
            result = scorer.score(ex["text"], ex["title"], ex["url"], ex["date"])
            assert result.score >= 0.25, (
                f"Score too low ({result.score}) for: {ex['title']}"
            )

    def test_oil_terms_detected(self, scorer):
        for ex in POSITIVE_EXAMPLES:
            result = scorer.score(ex["text"], ex["title"])
            assert result.food_terms_found, (
                f"No oil terms found in: {ex['title']}"
            )

    def test_adulteration_terms_detected(self, scorer):
        for ex in POSITIVE_EXAMPLES:
            result = scorer.score(ex["text"], ex["title"])
            assert result.adulteration_terms_found or result.action_terms_found, (
                f"No adulteration/action terms in: {ex['title']}"
            )


class TestNegativeExamples:
    def test_ecommerce_guide_is_irrelevant(self, scorer):
        ex = NEGATIVE_EXAMPLES[0]
        result = scorer.score(ex["text"], ex["title"], ex["url"])
        assert result.label == "irrelevant", (
            f"E-commerce guide should be irrelevant, got {result.label}"
        )

    def test_commodity_price_is_irrelevant(self, scorer):
        ex = NEGATIVE_EXAMPLES[1]
        result = scorer.score(ex["text"], ex["title"], ex["url"])
        assert result.label == "irrelevant"

    def test_purity_check_guide_is_irrelevant(self, scorer):
        ex = NEGATIVE_EXAMPLES[2]
        result = scorer.score(ex["text"], ex["title"], ex["url"])
        assert result.label == "irrelevant"


class TestURLPreFilter:
    def test_blocks_recipe_url(self):
        assert not url_looks_relevant("https://example.com/recipe/mustard-oil-chicken")

    def test_blocks_amazon(self):
        assert not url_looks_relevant("https://www.amazon.in/edible-oil/product/B123")

    def test_allows_news_article(self):
        assert url_looks_relevant(
            "https://timesofindia.indiatimes.com/city/lucknow/mustard-oil-adulteration",
            "6000 litres fake mustard oil seized UP",
        )

    def test_allows_fssai_article(self):
        assert url_looks_relevant(
            "https://theprint.in/india/fssai-edible-oil-raid/123/",
            "FSSAI seizes adulterated edible oil",
        )


class TestDateFilter:
    def test_date_in_range_bonus(self, scorer):
        in_range = scorer.score(
            "mustard oil adulteration seized FSSAI India Rajasthan",
            "Fake mustard oil seized India",
            publication_date="2024-06-01",
        )
        out_of_range = scorer.score(
            "mustard oil adulteration seized FSSAI India Rajasthan",
            "Fake mustard oil seized India",
            publication_date="2010-06-01",
        )
        assert in_range.score >= out_of_range.score
