export type RelevanceLabel = "relevant" | "irrelevant" | "pending";

export interface Article {
  article_id: string;
  slug: string;
  title: string;
  source?: string;
  date?: string;
  url?: string;
  raw_text?: string;
  cleaned_text?: string;
  food_keyword?: string;
  human_label: RelevanceLabel;
  label_source?: string;
  review_status?: string;
  classifier_label: RelevanceLabel;
  classifier_score?: number;
  classifier_model?: string;
  llm_event_present?: boolean;
  llm_validator_label?: string;
  llm_confidence?: number;
  food_item?: string;
  adulterant_or_issue?: string;
  location_city?: string;
  location_district?: string;
  location_state?: string;
  latitude?: number;
  longitude?: number;
  quantity?: string;
  authority_or_evidence?: string;
  action_taken?: string;
  date_of_incident?: string;
  quadrant?: string;
  ontology_id?: string;
  ontology_category?: string;
  evidence_excerpt?: string;
  notes?: string;
  round_number?: string;
  is_demo: boolean;
}

export type ArticleSummary = Omit<Article, "raw_text" | "cleaned_text"> & {
  excerpt?: string;
  search_text?: string;
};

export interface DashboardMetrics {
  total: number;
  reviewed: number;
  relevant: number;
  irrelevant: number;
  pending: number;
  categories: number;
  classifierScored: number;
  extractionComplete: number;
  extractionCoverage: number;
  locationCoverage: number;
}

export interface YearAggregate {
  year: string;
  total: number;
  relevant: number;
  irrelevant: number;
  pending: number;
  [category: string]: string | number;
}

export interface SourceAggregate {
  source: string;
  total: number;
  relevant: number;
}

export interface TaxonomyNode {
  id: string;
  name: string;
  definition: string;
  parent_id?: string;
  provisional?: boolean;
  fssai_relationship?: string;
  children?: TaxonomyNode[];
}

export interface TaxonomyData {
  status: "provisional" | "validated";
  updated_at?: string;
  food_categories: TaxonomyNode[];
  issue_categories: TaxonomyNode[];
}

export interface FssaiBaseline {
  id: string;
  title: string;
  short_title: string;
  year?: string;
  scope: string;
  tested_dimensions: string[];
  scope_notes: string[];
  source_url?: string;
  numerical_findings: Record<string, number | string>;
}

export interface DataProfile {
  isDemo: boolean;
  total: number;
  filename: string;
}
