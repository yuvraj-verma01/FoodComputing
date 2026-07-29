import { ArrowUpRight, CalendarDays, Newspaper } from "lucide-react";
import Link from "next/link";
import { ConfidenceBadge, StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import type { ArticleSummary } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export function ArticleCard({ article }: { article: ArticleSummary }) {
  return <article className="flex h-full flex-col border border-[var(--line)] bg-[var(--white)] p-5"><div className="flex flex-wrap items-center gap-2"><StatusBadge label={article.human_label} /><span className="rounded-full bg-[var(--paper-deep)] px-2.5 py-1 text-xs font-semibold">{article.food_keyword ?? "Uncategorised"}</span></div><h2 className="font-editorial mt-5 text-2xl leading-8 text-[var(--maroon-dark)]"><Link className="focus-ring hover:underline" href={`/incidents/${article.slug}`}>{article.title}</Link></h2><div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-[var(--muted)]"><span className="inline-flex items-center gap-1.5"><Newspaper className="h-3.5 w-3.5" />{article.source ?? "Source unavailable"}</span><span className="inline-flex items-center gap-1.5"><CalendarDays className="h-3.5 w-3.5" />{formatDate(article.date)}</span></div><p className="mt-5 line-clamp-4 text-sm leading-6 text-[var(--muted)]">{article.excerpt ?? "Article text is unavailable in the current export."}</p><div className="mt-auto flex items-end justify-between gap-4 pt-6"><div><p className="text-[10px] font-semibold uppercase tracking-[.08em] text-[var(--muted)]">Classifier confidence</p><div className="mt-1"><ConfidenceBadge score={article.classifier_score} /></div></div><Button asChild size="icon" variant="secondary" title="View incident analysis"><Link href={`/incidents/${article.slug}`} aria-label={`View incident analysis for ${article.title}`}><ArrowUpRight className="h-4 w-4" /></Link></Button></div></article>;
}
