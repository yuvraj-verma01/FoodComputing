"""Strict edible-oil adulteration relevance rules and LLM helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from typing import Any

import requests


EDIBLE_OIL_TERMS = [
    "edible oil",
    "cooking oil",
    "mustard oil",
    "refined oil",
    "soybean oil",
    "soya oil",
    "palm oil",
    "groundnut oil",
    "sesame oil",
    "sunflower oil",
    "rice bran oil",
    "cottonseed oil",
    "vegetable oil",
    "loose oil",
    "loose edible oil",
    "coconut oil",
    "olive oil",
    "rapeseed-mustard oil",
]

ADULTERATION_ACTION_TERMS = [
    "adulterated",
    "adulteration",
    "fake",
    "spurious",
    "contaminated",
    "contamination",
    "misbranded",
    "misbranding",
    "substandard",
    "unsafe",
    "rancid",
    "seized",
    "seizure",
    "raid",
    "raided",
    "sample failed",
    "samples failed",
    "failed test",
    "failed quality test",
    "failed safety test",
    "food safety",
    "FSSAI",
    "FDA",
    "FSDA",
    "Food Safety Department",
    "Food Safety Officer",
    "lab test",
    "quality test",
    "sample collected",
    "samples collected",
    "prosecution",
    "penalty",
    "fine",
    "banned",
    "shop sealed",
    "crackdown",
    "inspection",
]

ADULTERANT_TERMS = [
    "argemone oil",
    "mineral oil",
    "castor oil",
    "cottonseed oil",
    "palmolein",
    "cheap oil",
]

NON_FOOD_OIL_TERMS = [
    "petrol",
    "diesel",
    "crude oil",
    "engine oil",
    "lubricant",
    "kerosene",
    "fuel adulteration",
    "oil rig",
    "oil rigs",
    "oilfield",
    "offshore oil",
    "ONGC",
    "oil refinery",
    "refinery",
    "hair oil",
    "essential oil",
    "massage oil",
    "cosmetic oil",
    "aromatherapy oil",
]

BUSINESS_ONLY_TERMS = [
    "oil prices",
    "oil price",
    "edible oil prices",
    "oil imports",
    "oil exports",
    "import duty",
    "stock market",
    "commodity",
    "futures",
    "palm oil futures",
    "soybean futures",
    "market price",
    "price hike",
    "inflation",
]

NON_OIL_FOOD_TERMS = [
    "milk",
    "ghee",
    "paneer",
    "dairy products",
    "khoya",
    "mawa",
    "curd",
    "butter",
    "cheese",
    "spice",
    "spices",
    "turmeric",
    "chilli",
    "chili",
    "masala",
    "tea",
    "honey",
    "sweets",
    "flour",
    "atta",
    "soybean corn",
]

OUT_OF_SCOPE_FOOD_TERMS = [
    "ghee",
    "vanaspati",
]


@dataclass
class OilRelevanceDecision:
    rule_candidate: bool
    oil_role: str
    final_label: str
    confidence: float
    reason: str
    evidence_phrase: str
    edible_oil_terms: list[str]
    adulteration_action_terms: list[str]
    negative_terms: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["edible_oil_terms"] = "; ".join(self.edible_oil_terms)
        data["adulteration_action_terms"] = "; ".join(self.adulteration_action_terms)
        data["negative_terms"] = "; ".join(self.negative_terms)
        return data


def classify_oil_relevance(title: str = "", text: str = "", url: str = "") -> OilRelevanceDecision:
    """Classify whether edible oil is itself the adulterated food product."""
    combined = clean_text(" ".join([title or "", text or "", url or ""]))
    titleish = clean_text(" ".join([title or "", url or ""]))

    edible_hits = matching_terms(combined, EDIBLE_OIL_TERMS)
    action_hits = matching_terms(combined, ADULTERATION_ACTION_TERMS)
    non_food_hits = matching_terms(combined, NON_FOOD_OIL_TERMS)
    business_hits = matching_terms(combined, BUSINESS_ONLY_TERMS)
    out_scope_hits = matching_terms(combined, OUT_OF_SCOPE_FOOD_TERMS)

    if non_food_hits and not edible_hits:
        return decision(
            False,
            "non_food_oil",
            "irrelevant",
            0.95,
            "Non-food oil context dominates and no edible-oil product term is present.",
            evidence_for_terms(combined, non_food_hits),
            edible_hits,
            action_hits,
            non_food_hits,
        )

    if _non_food_oil_dominates(combined, non_food_hits, edible_hits):
        return decision(
            False,
            "non_food_oil",
            "irrelevant",
            0.90,
            "Non-food oil context such as fuel, crude, refinery, oil rig, or cosmetic oil dominates.",
            evidence_for_terms(combined, non_food_hits),
            edible_hits,
            action_hits,
            non_food_hits,
        )

    if _oil_as_adulterant(combined):
        return decision(
            True,
            "adulterant",
            "irrelevant",
            0.90,
            "Oil appears to be the adulterant used in another food product.",
            evidence_for_pattern(combined, ADULTERANT_ROLE_PATTERNS),
            edible_hits,
            action_hits,
            matching_terms(combined, NON_OIL_FOOD_TERMS),
        )

    if out_scope_hits and not edible_hits:
        return decision(
            False,
            "adjacent_or_unclear",
            "irrelevant",
            0.85,
            "Only out-of-scope dairy/vanaspati terms appear, not edible oil as the target product.",
            evidence_for_terms(combined, out_scope_hits),
            edible_hits,
            action_hits,
            out_scope_hits,
        )

    if business_hits and not action_hits:
        return decision(
            False,
            "adjacent_or_unclear",
            "irrelevant",
            0.85,
            "Business/price/import context with no adulteration or enforcement signal.",
            evidence_for_terms(combined, business_hits),
            edible_hits,
            action_hits,
            business_hits,
        )

    strong_evidence = evidence_for_pattern(combined, ADULTERATED_PRODUCT_PATTERNS)
    if strong_evidence:
        return decision(
            True,
            "adulterated_product",
            "relevant",
            0.94,
            "Pattern says edible oil is the adulterated/seized/failed product.",
            strong_evidence,
            edible_hits,
            action_hits,
            [],
        )

    close_evidence = proximity_evidence(combined, EDIBLE_OIL_TERMS, ADULTERATION_ACTION_TERMS, window=90)
    if edible_hits and action_hits and close_evidence:
        confidence = 0.82 if close_evidence in titleish else 0.74
        return decision(
            True,
            "adulterated_product",
            "relevant" if confidence >= 0.80 else "manual_review",
            confidence,
            "Edible-oil term appears close to adulteration/enforcement language.",
            close_evidence,
            edible_hits,
            action_hits,
            [],
        )

    if edible_hits and action_hits:
        return decision(
            True,
            "adjacent_or_unclear",
            "manual_review",
            0.55,
            "Edible-oil and adulteration/action terms both appear, but product role is not clear.",
            evidence_for_terms(combined, edible_hits + action_hits),
            edible_hits,
            action_hits,
            [],
        )

    if edible_hits:
        return decision(
            False,
            "adjacent_or_unclear",
            "irrelevant",
            0.70,
            "Edible-oil term appears without an adulteration/enforcement signal.",
            evidence_for_terms(combined, edible_hits),
            edible_hits,
            action_hits,
            business_hits,
        )

    if action_hits:
        return decision(
            False,
            "adjacent_or_unclear",
            "irrelevant",
            0.70,
            "Adulteration/enforcement signal appears without an edible-oil product term.",
            evidence_for_terms(combined, action_hits),
            edible_hits,
            action_hits,
            non_food_hits,
        )

    return decision(
        False,
        "adjacent_or_unclear",
        "irrelevant",
        0.80,
        "No edible-oil adulteration signal found.",
        "",
        edible_hits,
        action_hits,
        non_food_hits + business_hits,
    )


def ollama_relevance_check(
    *,
    title: str,
    text: str,
    url: str,
    model: str = "llama3.1:8b-instruct-q4_K_M",
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    """Ask a local Ollama model to read and classify one extracted article."""
    prompt = build_llm_prompt(title=title, text=text, url=url)
    response = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    raw = payload.get("response") or "{}"
    parsed = _parse_json_object(raw)
    return {
        "llm_label": str(parsed.get("label") or "unclear").lower(),
        "llm_confidence": _safe_float(parsed.get("confidence"), default=0.0),
        "llm_reason": str(parsed.get("reason") or "")[:800],
        "evidence_phrase": str(parsed.get("evidence_phrase") or "")[:500],
        "llm_model": model,
        "llm_raw": raw[:2000],
    }


def build_llm_prompt(title: str, text: str, url: str) -> str:
    trimmed = clean_text(text)[:6500]
    return f"""
You are classifying Indian news articles for a food adulteration research corpus.

Strict relevant definition:
Relevant ONLY if edible oil/cooking oil/mustard oil/refined oil/palm oil/soybean oil/groundnut oil/sesame oil/sunflower oil/rice bran oil/cottonseed oil/coconut oil/olive oil is itself the adulterated, fake, spurious, unsafe, misbranded, seized, or failed-sample food product.

Irrelevant if:
- oil is merely an adulterant in another food like milk, paneer, ghee, spices, or sweets
- petrol, diesel, crude oil, engine oil, hair oil, essential oil, cosmetic oil, oil rigs, or refinery context
- edible oil price/import/business story with no adulteration incident
- general food safety article that only mentions oil in a list
- ghee or vanaspati-only story

Return only this JSON object:
{{
  "label": "relevant" | "irrelevant" | "unclear",
  "confidence": 0.0,
  "reason": "short reason",
  "evidence_phrase": "short quote or phrase from the article supporting the label"
}}

Title: {title}
URL: {url}
Article text:
{trimmed}
""".strip()


def merge_rule_and_llm(rule: OilRelevanceDecision, llm: dict[str, Any] | None) -> dict[str, Any]:
    """Merge rule and LLM decisions without letting LLM override hard exclusions casually."""
    data = rule.to_dict()
    if not llm:
        data.update(
            {
                "llm_label": "",
                "llm_confidence": "",
                "llm_reason": "",
                "llm_model": "",
            }
        )
        return data

    llm_label = str(llm.get("llm_label") or "unclear").lower()
    llm_conf = _safe_float(llm.get("llm_confidence"), default=0.0)
    llm_reason = str(llm.get("llm_reason") or "")
    llm_evidence = str(llm.get("evidence_phrase") or "")

    final_label = rule.final_label
    confidence = rule.confidence
    reason = rule.reason
    evidence = rule.evidence_phrase

    hard_exclusion = rule.oil_role in {"adulterant", "non_food_oil"}
    if not hard_exclusion and llm_label in {"relevant", "irrelevant"} and llm_conf >= 0.65:
        final_label = llm_label
        confidence = max(rule.confidence, llm_conf)
        reason = f"LLM reading: {llm_reason}"
        evidence = llm_evidence or evidence
    elif hard_exclusion and llm_label == "relevant" and llm_conf >= 0.90 and llm_evidence:
        final_label = "manual_review"
        confidence = 0.60
        reason = "Rule hard-excluded this row, but LLM found possible contrary evidence; needs manual review."
        evidence = llm_evidence

    data.update(
        {
            "final_label": final_label,
            "confidence": round(confidence, 3),
            "reason": reason,
            "evidence_phrase": evidence,
            "llm_label": llm_label,
            "llm_confidence": llm_conf,
            "llm_reason": llm_reason,
            "llm_model": llm.get("llm_model", ""),
        }
    )
    return data


ADULTERATED_PRODUCT_PATTERNS = [
    re.compile(
        r"\b(?:edible|cooking|mustard|refined|soy(?:a|bean)|palm|groundnut|sesame|sunflower|rice bran|cottonseed|vegetable|coconut|olive|loose)\s+oil(?:s)?\b.{0,90}\b(?:adulterat\w*|fake|spurious|contaminat\w*|misbrand\w*|substandard|unsafe|seiz\w*|raid\w*|failed|sample|samples)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:adulterat\w*|fake|spurious|contaminat\w*|misbrand\w*|substandard|unsafe|seiz\w*|raid\w*|failed)\b.{0,90}\b(?:edible|cooking|mustard|refined|soy(?:a|bean)|palm|groundnut|sesame|sunflower|rice bran|cottonseed|vegetable|coconut|olive|loose)\s+oil(?:s)?\b",
        re.I,
    ),
    re.compile(r"\boil\s+samples?\b.{0,70}\b(?:failed|unsafe|substandard|misbrand\w*|adulterat\w*)\b", re.I),
    re.compile(r"\b(?:fake|spurious|adulterated|unsafe)\s+oil\b", re.I),
]

ADULTERANT_ROLE_PATTERNS = [
    re.compile(
        r"\b(?:milk|ghee|paneer|khoya|mawa|spices?|turmeric|chilli|chili|masala|sweets?|tea|honey|flour|atta)\b.{0,90}\b(?:adulterat\w*|mixed)\s+(?:with|using|by adding)\s+(?:oil|argemone oil|palm oil|vegetable oil)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:oil|argemone oil|palm oil|vegetable oil)\b.{0,70}\b(?:used|added|mixed)\s+(?:in|into|with|to)\s+(?:milk|ghee|paneer|khoya|mawa|spices?|turmeric|chilli|chili|masala|sweets?|tea|honey|flour|atta)\b",
        re.I,
    ),
]


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def matching_terms(text: str, terms: list[str]) -> list[str]:
    found = []
    for term in terms:
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        if re.search(pattern, text.lower()):
            found.append(term)
    return found


def proximity_evidence(text: str, left_terms: list[str], right_terms: list[str], window: int = 90) -> str:
    lowered = text.lower()
    for left in left_terms:
        for right in right_terms:
            for match in re.finditer(re.escape(left.lower()), lowered):
                start = max(0, match.start() - window)
                end = min(len(text), match.end() + window)
                snippet = text[start:end]
                if re.search(r"\b" + re.escape(right.lower()) + r"\b", snippet.lower()):
                    return snippet.strip()
    return ""


def evidence_for_terms(text: str, terms: list[str]) -> str:
    lowered = text.lower()
    for term in terms:
        idx = lowered.find(term.lower())
        if idx >= 0:
            start = max(0, idx - 100)
            end = min(len(text), idx + len(term) + 140)
            return text[start:end].strip()
    return ""


def evidence_for_pattern(text: str, patterns: list[re.Pattern]) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - 80)
            end = min(len(text), match.end() + 100)
            return text[start:end].strip()
    return ""


def decision(
    rule_candidate: bool,
    oil_role: str,
    final_label: str,
    confidence: float,
    reason: str,
    evidence_phrase: str,
    edible_hits: list[str],
    action_hits: list[str],
    negative_hits: list[str],
) -> OilRelevanceDecision:
    return OilRelevanceDecision(
        rule_candidate=rule_candidate,
        oil_role=oil_role,
        final_label=final_label,
        confidence=round(confidence, 3),
        reason=reason,
        evidence_phrase=evidence_phrase,
        edible_oil_terms=edible_hits,
        adulteration_action_terms=action_hits,
        negative_terms=negative_hits,
    )


def _non_food_oil_dominates(text: str, non_food_hits: list[str], edible_hits: list[str]) -> bool:
    if not non_food_hits:
        return False
    if not edible_hits:
        return True
    non_food_evidence = evidence_for_terms(text, non_food_hits)
    edible_evidence = evidence_for_terms(text, edible_hits)
    return bool(non_food_evidence and not edible_evidence)


def _oil_as_adulterant(text: str) -> bool:
    return any(pattern.search(text) for pattern in ADULTERANT_ROLE_PATTERNS)


def _parse_json_object(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
