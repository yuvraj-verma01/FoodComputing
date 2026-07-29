import { AlertCircle, ArrowRight, BarChart3, Database, FileQuestion, Info, type LucideIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { ConfidenceBadge, StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import type { Article, FssaiBaseline } from "@/lib/types";
import { cn, formatDate, formatNumber, formatPercent } from "@/lib/utils";

export function DemoBanner() {
  return <div className="border-b border-amber-700/25 bg-amber-50 px-4 py-3 text-center text-sm font-medium text-amber-950"><span className="inline-flex items-center gap-2"><Info className="h-4 w-4" />Demonstration data is currently displayed. Replace <code>/data/articles.csv</code> with the validated project corpus.</span></div>;
}

export function PageIntro({ eyebrow, title, description, aside }: { eyebrow: string; title: string; description: string; aside?: ReactNode }) {
  return <section className="border-b border-[var(--line)] bg-[var(--white)]"><div className="section-shell grid gap-10 py-14 md:grid-cols-[minmax(0,1fr)_minmax(16rem,.42fr)] md:py-20"><div><p className="eyebrow rule-label">{eyebrow}</p><h1 className="font-editorial mt-6 max-w-4xl text-4xl leading-[1.08] text-[var(--maroon-dark)] sm:text-5xl lg:text-6xl">{title}</h1><p className="mt-6 max-w-3xl text-lg leading-8 text-[var(--muted)]">{description}</p></div>{aside && <div className="self-end border-l-2 border-[var(--saffron)] pl-5 text-sm leading-6 text-[var(--muted)]">{aside}</div>}</div></section>;
}

export function SectionHeading({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h2 className="font-editorial mt-2 text-3xl leading-tight text-[var(--maroon-dark)] md:text-4xl">{title}</h2>{description && <p className="mt-3 max-w-2xl leading-7 text-[var(--muted)]">{description}</p>}</div>{action}</div>;
}

export function MetricCard({ label, value, note, icon: Icon = BarChart3 }: { label: string; value: number | string; note?: string; icon?: LucideIcon }) {
  return <div className="border border-[var(--line)] bg-[var(--white)] p-5"><div className="flex items-start justify-between gap-4"><p className="text-sm font-medium text-[var(--muted)]">{label}</p><Icon className="h-4 w-4 text-[var(--saffron)]" /></div><p className="font-editorial mt-6 text-4xl text-[var(--maroon-dark)]">{typeof value === "number" ? formatNumber(value) : value}</p>{note && <p className="mt-2 text-xs leading-5 text-[var(--muted)]">{note}</p>}</div>;
}

export function CoverageCard({ title, status, progress, stats, tone }: { title: string; status: string; progress: number; stats: string; tone: "complete" | "progress" }) {
  return <article className="border-t-4 border-[var(--maroon)] bg-[var(--white)] p-6"><div className="flex items-center justify-between gap-3"><h3 className="font-editorial text-2xl text-[var(--maroon-dark)]">{title}</h3><StatusBadge label={tone === "complete" ? "Complete" : "In progress"} /></div><p className="mt-5 min-h-12 text-sm leading-6 text-[var(--muted)]">{status}</p><div className="mt-7 h-1.5 overflow-hidden bg-[var(--paper-deep)]" aria-label={`${Math.round(progress * 100)} percent complete`}><div className="h-full bg-[var(--saffron)]" style={{ width: `${Math.round(progress * 100)}%` }} /></div><p className="mt-3 text-xs font-medium text-[var(--muted)]">{stats}</p></article>;
}

export function DataAvailabilityNotice({ title, children, progress }: { title: string; children: ReactNode; progress?: number }) {
  return <div className="grid min-h-72 place-items-center border border-dashed border-[var(--line)] bg-[var(--white)] p-8 text-center"><div className="max-w-xl"><Database className="mx-auto h-8 w-8 text-[var(--saffron)]" /><h2 className="font-editorial mt-5 text-2xl text-[var(--maroon-dark)]">{title}</h2><div className="mt-3 text-sm leading-6 text-[var(--muted)]">{children}</div>{progress !== undefined && <div className="mt-7"><div className="h-2 overflow-hidden bg-[var(--paper-deep)]"><div className="h-full bg-[var(--sage)]" style={{ width: `${Math.max(1, Math.round(progress * 100))}%` }} /></div><p className="mt-2 text-xs">{formatPercent(progress, 1)} of records currently mapped</p></div>}</div></div>;
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="grid min-h-64 place-items-center border border-dashed border-[var(--line)] p-8 text-center"><div><FileQuestion className="mx-auto h-7 w-7 text-[var(--muted)]" /><h3 className="font-editorial mt-4 text-2xl">{title}</h3><p className="mt-2 max-w-lg text-sm leading-6 text-[var(--muted)]">{description}</p></div></div>;
}

export function ExtractionField({ label, value }: { label: string; value?: ReactNode }) {
  const available = value !== undefined && value !== null && value !== "";
  return <div className="border-b border-[var(--line)] py-4 last:border-0"><dt className="text-xs font-semibold uppercase tracking-[.08em] text-[var(--muted)]">{label}</dt><dd className={cn("mt-1.5 text-sm leading-6", !available && "italic text-[var(--muted)]")}>{available ? value : "Not yet extracted"}</dd></div>;
}

export function ArticleMetadata({ article }: { article: Article }) {
  return <dl className="grid gap-x-8 border-y border-[var(--line)] sm:grid-cols-2 lg:grid-cols-4"><ExtractionField label="Source" value={article.source} /><ExtractionField label="Publication date" value={article.date ? formatDate(article.date) : undefined} /><ExtractionField label="Food category" value={article.food_keyword} /><ExtractionField label="Human review label" value={<StatusBadge label={article.human_label} />} /><ExtractionField label="Classifier output" value={article.classifier_label === "pending" ? undefined : <StatusBadge label={article.classifier_label} />} /><ExtractionField label="Classifier confidence" value={article.classifier_score === undefined ? undefined : <ConfidenceBadge score={article.classifier_score} />} /><ExtractionField label="Classifier model" value={article.classifier_model} /><ExtractionField label="Review provenance" value={article.label_source} /></dl>;
}

export function LimitationsPanel({ children }: { children: ReactNode }) {
  return <aside className="border-l-4 border-[var(--saffron)] bg-[#fff7e9] p-6"><div className="flex gap-3"><AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-[var(--saffron)]" /><div><h3 className="font-semibold text-[var(--maroon-dark)]">Interpretation note</h3><div className="mt-2 text-sm leading-6 text-[var(--muted)]">{children}</div></div></div></aside>;
}

export function DataQualityPanel({ total, reviewed, scored, extraction }: { total: number; reviewed: number; scored: number; extraction: number }) {
  const rows = [["Human review", reviewed / total], ["Classifier score", scored / total], ["Event extraction", extraction / total]] as const;
  return <div className="border border-[var(--line)] bg-[var(--white)] p-6"><div className="flex items-center gap-3"><Database className="h-5 w-5 text-[var(--maroon)]" /><h3 className="font-semibold">Current data completion</h3></div><div className="mt-6 space-y-5">{rows.map(([label, value]) => <div key={label}><div className="flex justify-between text-sm"><span>{label}</span><span className="font-semibold">{formatPercent(value, 1)}</span></div><div className="mt-2 h-1.5 bg-[var(--paper-deep)]"><div className="h-full bg-[var(--sage)]" style={{ width: `${Math.round(value * 100)}%` }} /></div></div>)}</div></div>;
}

export function FSSAIComparisonCard({ baseline }: { baseline: FssaiBaseline }) {
  return <article className="border border-[var(--line)] bg-[var(--white)]"><div className="border-b border-[var(--line)] p-6"><p className="eyebrow">Official baseline</p><h2 className="font-editorial mt-3 text-3xl text-[var(--maroon-dark)]">{baseline.title}</h2><p className="mt-4 leading-7 text-[var(--muted)]">{baseline.scope}</p></div><div className="grid gap-8 p-6 md:grid-cols-2"><div><h3 className="text-sm font-semibold">Tested dimensions</h3><ul className="mt-4 grid gap-2 text-sm text-[var(--muted)]">{baseline.tested_dimensions.map((item) => <li className="flex gap-2" key={item}><span className="mt-2 h-1.5 w-1.5 shrink-0 bg-[var(--saffron)]" />{item}</li>)}</ul></div><div><h3 className="text-sm font-semibold">Scope notes</h3><ul className="mt-4 grid gap-3 text-sm leading-6 text-[var(--muted)]">{baseline.scope_notes.map((item) => <li key={item}>{item}</li>)}</ul>{Object.keys(baseline.numerical_findings).length === 0 && <p className="mt-5 border-t border-[var(--line)] pt-4 text-xs font-medium text-[var(--maroon)]">No numerical findings are loaded.</p>}</div></div></article>;
}

export function MethodologyStep({ number, title, status, children }: { number: string; title: string; status: string; children: ReactNode }) {
  return <article className="grid gap-4 border-t border-[var(--line)] py-7 sm:grid-cols-[3rem_1fr_auto]"><span className="font-editorial text-2xl text-[var(--saffron)]">{number}</span><div><h3 className="font-editorial text-2xl text-[var(--maroon-dark)]">{title}</h3><div className="mt-2 text-sm leading-6 text-[var(--muted)]">{children}</div></div><StatusBadge label={status} className="self-start" /></article>;
}

export function ExploreLink({ href, children }: { href: string; children: ReactNode }) {
  return <Button asChild variant="secondary"><Link href={href}>{children}<ArrowRight className="h-4 w-4" /></Link></Button>;
}
