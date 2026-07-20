import { ArrowLeft, ExternalLink, Quote, ShieldAlert } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ArticleMetadata, ExtractionField, LimitationsPanel } from "@/components/research-ui";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { getArticleBySlug } from "@/lib/data-loader";
import { formatDate, formatPercent } from "@/lib/utils";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const article = getArticleBySlug(slug);
  return { title: article?.title ?? "Article record" };
}

export default async function ArticleDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = getArticleBySlug(slug);
  if (!article) notFound();
  const articleText = article.cleaned_text ?? article.raw_text;

  return <>
    <section className="border-b border-[var(--line)] bg-[var(--white)]"><div className="section-shell py-12 md:py-16"><Link href="/incidents" className="focus-ring inline-flex items-center gap-2 text-sm font-semibold text-[var(--maroon)]"><ArrowLeft className="h-4 w-4" />Back to incidents</Link><div className="mt-10 flex flex-wrap gap-2"><StatusBadge label={article.human_label} /><span className="rounded-full bg-[var(--paper-deep)] px-2.5 py-1 text-xs font-semibold">{article.food_keyword ?? "Uncategorised"}</span></div><h1 className="font-editorial mt-6 max-w-5xl text-4xl leading-tight text-[var(--maroon-dark)] md:text-6xl">{article.title}</h1><div className="mt-7 flex flex-wrap items-center gap-4 text-sm text-[var(--muted)]"><span>{article.source ?? "Source unavailable"}</span><span aria-hidden="true">·</span><span>{formatDate(article.date)}</span>{article.url && <Button asChild variant="secondary" size="sm"><a href={article.url} target="_blank" rel="noreferrer">Original article <ExternalLink className="h-3.5 w-3.5" /></a></Button>}</div></div></section>

    <div className="section-shell py-12"><ArticleMetadata article={article} />
      <div className="mt-12 grid gap-10 lg:grid-cols-[minmax(0,1fr)_22rem]"><div className="min-w-0"><section><p className="eyebrow">Incident analysis</p><h2 className="font-editorial mt-3 text-3xl text-[var(--maroon-dark)]">Structured extraction record</h2><p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--muted)]">Fields remain visible when empty so the interface can accept validated extraction outputs without changing its structure.</p><dl className="mt-7 grid gap-x-8 border-y border-[var(--line)] sm:grid-cols-2"><ExtractionField label="Large-model event present" value={article.llm_event_present === undefined ? undefined : article.llm_event_present ? "Yes" : "No"} /><ExtractionField label="Large-model validator label" value={article.llm_validator_label} /><ExtractionField label="Large-model confidence" value={article.llm_confidence === undefined ? undefined : formatPercent(article.llm_confidence, 1)} /><ExtractionField label="Food item" value={article.food_item} /><ExtractionField label="Adulterant or issue" value={article.adulterant_or_issue} /><ExtractionField label="City" value={article.location_city} /><ExtractionField label="District" value={article.location_district} /><ExtractionField label="State" value={article.location_state} /><ExtractionField label="Quantity" value={article.quantity} /><ExtractionField label="Authority or evidence" value={article.authority_or_evidence} /><ExtractionField label="Action taken" value={article.action_taken} /><ExtractionField label="Date of incident" value={article.date_of_incident ? formatDate(article.date_of_incident) : undefined} /><ExtractionField label="TP / FP / TN / FN quadrant" value={article.quadrant} /><ExtractionField label="Notes" value={article.notes} /><ExtractionField label="Ontology identifier" value={article.ontology_id} /><ExtractionField label="Ontology mapping" value={article.ontology_category} /></dl></section>

        <section className="mt-12"><div className="flex items-center gap-3"><Quote className="h-5 w-5 text-[var(--saffron)]" /><h2 className="font-editorial text-3xl text-[var(--maroon-dark)]">Evidence used for classification</h2></div>{article.evidence_excerpt ? <blockquote className="mt-6 border-l-2 border-[var(--saffron)] pl-5 text-lg leading-8">{article.evidence_excerpt}</blockquote> : <p className="mt-5 border border-dashed border-[var(--line)] bg-[var(--white)] p-5 text-sm italic text-[var(--muted)]">Evidence-span extraction has not yet been run for this article.</p>}</section>

        <section className="mt-12"><p className="eyebrow">Article text</p><h2 className="font-editorial mt-3 text-3xl text-[var(--maroon-dark)]">Cleaned research copy</h2>{articleText ? <div className="mt-6 whitespace-pre-wrap border border-[var(--line)] bg-[var(--white)] p-6 text-[15px] leading-8 md:p-9">{articleText}</div> : <p className="mt-6 border border-dashed border-[var(--line)] p-6 text-sm italic text-[var(--muted)]">Cleaned article text is unavailable in this export.</p>}</section></div>

      <aside className="space-y-6"><div className="border border-[var(--line)] bg-[var(--white)] p-6"><h2 className="font-semibold">Record identifiers</h2><dl className="mt-4"><ExtractionField label="Article ID" value={<code className="break-all text-xs">{article.article_id}</code>} /><ExtractionField label="Research round" value={article.round_number} /><ExtractionField label="Review status" value={article.review_status} /></dl></div><LimitationsPanel>{article.food_keyword === "Ghee" && article.classifier_model?.includes("transfer") ? "This classifier output is an unchanged transfer test from the edible-oil model. It is not a calibrated ghee-specific classifier." : "Classifier scores are model outputs and should be interpreted alongside human labels and the documented validation protocol."}</LimitationsPanel></aside></div>

      <div className="mt-12 flex gap-4 border border-red-900/20 bg-red-50 p-6 text-sm leading-6 text-red-950"><ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" /><p><strong>Research annotation disclaimer.</strong> Classification and extraction outputs are research annotations. They should not be treated as independent verification of the claims contained in the original news report.</p></div>
    </div></>;
}
