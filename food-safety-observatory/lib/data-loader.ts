import "server-only";

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import { cache } from "react";
import Papa from "papaparse";

import type {
  Article,
  ArticleSummary,
  DashboardMetrics,
  DataProfile,
  FssaiBaseline,
  RelevanceLabel,
  SourceAggregate,
  TaxonomyData,
  YearAggregate,
} from "@/lib/types";
import { getExcerpt } from "@/lib/utils";

const DATA_DIR = process.env.OBSERVATORY_DATA_DIR
  ? path.resolve(process.env.OBSERVATORY_DATA_DIR)
  : path.join(process.cwd(), "data");

const MISSING_VALUES = new Set(["", "nan", "null", "none", "n/a", "na", "undefined"]);

function clean(value: unknown): string | undefined {
  if (value === null || value === undefined) return undefined;
  const output = String(value).trim();
  return MISSING_VALUES.has(output.toLowerCase()) ? undefined : output;
}

function number(value: unknown): number | undefined {
  const output = clean(value);
  if (!output) return undefined;
  const parsed = Number(output);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function boolean(value: unknown): boolean | undefined {
  const output = clean(value)?.toLowerCase();
  if (!output) return undefined;
  if (["true", "1", "yes", "y"].includes(output)) return true;
  if (["false", "0", "no", "n"].includes(output)) return false;
  return undefined;
}

export function normalizeLabel(value: unknown): RelevanceLabel {
  const output = clean(value)?.toLowerCase();
  if (!output) return "pending";
  if (["1", "relevant", "positive", "keep", "yes", "true"].includes(output)) return "relevant";
  if (["0", "irrelevant", "negative", "drop", "no", "false"].includes(output)) return "irrelevant";
  return "pending";
}

function date(value: unknown): string | undefined {
  const output = clean(value);
  if (!output) return undefined;
  const parsed = new Date(output);
  if (Number.isNaN(parsed.getTime())) return undefined;
  return parsed.toISOString().slice(0, 10);
}

function slugify(value: string) {
  const slug = value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 80);
  return slug || createHash("sha1").update(value).digest("hex").slice(0, 16);
}

function normalizeRow(row: Record<string, unknown>, index: number): Article {
  const fallback = clean(row.url) ?? `${clean(row.title) ?? "article"}-${index}`;
  const articleId = clean(row.article_id) ?? createHash("sha1").update(fallback).digest("hex");
  return {
    article_id: articleId,
    slug: slugify(articleId),
    title: clean(row.title) ?? "Untitled article",
    source: clean(row.source),
    date: date(row.date ?? row.publication_date),
    url: clean(row.url),
    raw_text: clean(row.raw_text),
    cleaned_text: clean(row.cleaned_text ?? row.article_text),
    food_keyword: clean(row.food_keyword),
    human_label: normalizeLabel(row.human_label ?? row.final_keep ?? row.keep),
    label_source: clean(row.label_source),
    review_status: clean(row.review_status),
    classifier_label: normalizeLabel(row.classifier_label),
    classifier_score: number(row.classifier_score),
    classifier_model: clean(row.classifier_model),
    llm_event_present: boolean(row.llm_event_present),
    llm_validator_label: clean(row.llm_validator_label),
    llm_confidence: number(row.llm_confidence),
    food_item: clean(row.food_item),
    adulterant_or_issue: clean(row.adulterant_or_issue),
    location_city: clean(row.location_city),
    location_district: clean(row.location_district),
    location_state: clean(row.location_state),
    latitude: number(row.latitude),
    longitude: number(row.longitude),
    quantity: clean(row.quantity),
    authority_or_evidence: clean(row.authority_or_evidence),
    action_taken: clean(row.action_taken),
    date_of_incident: date(row.date_of_incident),
    quadrant: clean(row.quadrant),
    ontology_id: clean(row.ontology_id),
    ontology_category: clean(row.ontology_category),
    evidence_excerpt: clean(row.evidence_excerpt),
    notes: clean(row.notes),
    round_number: clean(row.round_number),
    is_demo: boolean(row.is_demo) ?? false,
  };
}

export const getArticles = cache((): Article[] => {
  const parsed = Papa.parse<Record<string, unknown>>(
    readFileSync(path.join(DATA_DIR, "articles.csv"), "utf8"),
    { header: true, skipEmptyLines: "greedy", transformHeader: (header) => header.trim().toLowerCase() },
  );
  if (parsed.errors.length) {
    const first = parsed.errors[0];
    throw new Error(`Unable to parse articles.csv at row ${first.row ?? "unknown"}: ${first.message}`);
  }
  return parsed.data.map(normalizeRow);
});

export const getArticleBySlug = cache((slug: string) =>
  getArticles().find((article) => article.slug === slug),
);

export function toArticleSummaries(articles: Article[]): ArticleSummary[] {
  return articles.map(({ raw_text, cleaned_text, ...article }) => ({
    ...article,
    excerpt: getExcerpt(cleaned_text ?? raw_text),
    search_text: cleaned_text ?? raw_text,
  }));
}

export function getDataProfile(articles = getArticles()): DataProfile {
  return {
    isDemo: articles.length > 0 && articles.every((article) => article.is_demo),
    total: articles.length,
    filename: "articles.csv",
  };
}

export function getMetrics(articles = getArticles()): DashboardMetrics {
  const reviewed = articles.filter((article) => article.human_label !== "pending");
  const extractionComplete = articles.filter(
    (article) => article.food_item || article.adulterant_or_issue || article.action_taken,
  ).length;
  const located = articles.filter((article) => article.location_state).length;
  return {
    total: articles.length,
    reviewed: reviewed.length,
    relevant: reviewed.filter((article) => article.human_label === "relevant").length,
    irrelevant: reviewed.filter((article) => article.human_label === "irrelevant").length,
    pending: articles.length - reviewed.length,
    categories: new Set(articles.map((article) => article.food_keyword).filter(Boolean)).size,
    classifierScored: articles.filter((article) => article.classifier_score !== undefined).length,
    extractionComplete,
    extractionCoverage: articles.length ? extractionComplete / articles.length : 0,
    locationCoverage: articles.length ? located / articles.length : 0,
  };
}

export function getYearAggregates(articles = getArticles()): YearAggregate[] {
  const years = new Map<string, YearAggregate>();
  for (const article of articles) {
    if (!article.date) continue;
    const year = article.date.slice(0, 4);
    const current = years.get(year) ?? { year, total: 0, relevant: 0, irrelevant: 0, pending: 0 };
    current.total += 1;
    current[article.human_label] += 1;
    const category = article.food_keyword ?? "Uncategorised";
    current[category] = Number(current[category] ?? 0) + 1;
    years.set(year, current);
  }
  return [...years.values()].sort((a, b) => a.year.localeCompare(b.year));
}

export function getSourceAggregates(articles = getArticles()): SourceAggregate[] {
  const sources = new Map<string, SourceAggregate>();
  for (const article of articles) {
    const source = article.source ?? "Unknown source";
    const current = sources.get(source) ?? { source, total: 0, relevant: 0 };
    current.total += 1;
    if (article.human_label === "relevant") current.relevant += 1;
    sources.set(source, current);
  }
  return [...sources.values()].sort((a, b) => b.total - a.total);
}

export function getStateAggregates(articles = getArticles()) {
  const states = new Map<string, { state: string; total: number; articles: ArticleSummary[] }>();
  for (const article of articles) {
    if (!article.location_state) continue;
    const current = states.get(article.location_state) ?? { state: article.location_state, total: 0, articles: [] };
    current.total += 1;
    current.articles.push(...toArticleSummaries([article]));
    states.set(article.location_state, current);
  }
  return [...states.values()].sort((a, b) => b.total - a.total);
}

export const getTaxonomy = cache((): TaxonomyData =>
  JSON.parse(readFileSync(path.join(DATA_DIR, "taxonomy.json"), "utf8")) as TaxonomyData,
);

export const getFssaiBaselines = cache((): FssaiBaseline[] =>
  JSON.parse(readFileSync(path.join(DATA_DIR, "fssai-baselines.json"), "utf8")) as FssaiBaseline[],
);
