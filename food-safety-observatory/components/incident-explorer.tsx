"use client";

import { ChevronLeft, ChevronRight, Grid2X2, List, Search, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";

import { ArticleCard } from "@/components/article-card";
import { ArticleTable } from "@/components/article-table";
import { ExplorerFilters, FilterSidebar } from "@/components/filter-sidebar";
import { EmptyState } from "@/components/research-ui";
import { Button } from "@/components/ui/button";
import type { ArticleSummary } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";

const PAGE_SIZE = 12;
const initialFilters: ExplorerFilters = { category: "all", relevance: "relevant", source: "all", year: "all", confidence: "all" };

export function IncidentExplorer({ articles }: { articles: ArticleSummary[] }) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState(initialFilters);
  const [sort, setSort] = useState("newest");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [page, setPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const categories = useMemo(() => [...new Set(articles.map((article) => article.food_keyword).filter((value): value is string => Boolean(value)))].sort(), [articles]);
  const sources = useMemo(() => [...new Set(articles.map((article) => article.source).filter((value): value is string => Boolean(value)))].sort(), [articles]);
  const years = useMemo(() => [...new Set(articles.map((article) => article.date?.slice(0, 4)).filter((value): value is string => Boolean(value)))].sort().reverse(), [articles]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const output = articles.filter((article) => {
      const haystack = `${article.title} ${article.source ?? ""} ${article.search_text ?? ""}`.toLowerCase();
      if (needle && !haystack.includes(needle)) return false;
      if (filters.category !== "all" && article.food_keyword !== filters.category) return false;
      if (filters.relevance !== "all" && article.human_label !== filters.relevance) return false;
      if (filters.source !== "all" && article.source !== filters.source) return false;
      if (filters.year !== "all" && article.date?.slice(0, 4) !== filters.year) return false;
      if (filters.confidence !== "all" && (article.classifier_score === undefined || article.classifier_score < Number(filters.confidence))) return false;
      return true;
    });
    output.sort((a, b) => {
      if (sort === "oldest") return (a.date ?? "9999").localeCompare(b.date ?? "9999");
      if (sort === "confidence") return (b.classifier_score ?? -1) - (a.classifier_score ?? -1);
      if (sort === "title") return a.title.localeCompare(b.title);
      return (b.date ?? "0000").localeCompare(a.date ?? "0000");
    });
    return output;
  }, [articles, filters, query, sort]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const updateFilter = (key: keyof ExplorerFilters, value: string) => { setFilters((current) => ({ ...current, [key]: value })); setPage(1); };
  const clearAll = () => { setQuery(""); setFilters({ category: "all", relevance: "all", source: "all", year: "all", confidence: "all" }); setPage(1); };

  return <div className="section-shell py-10"><div className="relative"><Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-[var(--muted)]" /><input className="focus-ring h-14 w-full rounded-[4px] border border-[var(--line)] bg-white pl-12 pr-4 text-base" type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="Search titles, sources and full article text" aria-label="Search article repository" /></div><div className="mt-4 flex flex-wrap items-center justify-between gap-3"><Button variant="secondary" className="lg:hidden" onClick={() => setFiltersOpen(!filtersOpen)}><SlidersHorizontal className="h-4 w-4" />Filters</Button><p className="text-sm text-[var(--muted)]"><strong className="text-[var(--ink)]">{formatNumber(filtered.length)}</strong> results</p><div className="flex items-center gap-2"><label className="sr-only" htmlFor="sort-results">Sort results</label><select id="sort-results" className="focus-ring h-10 rounded-[4px] border border-[var(--line)] bg-white px-3 text-sm" value={sort} onChange={(event) => { setSort(event.target.value); setPage(1); }}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="confidence">Highest confidence</option><option value="title">Title A-Z</option></select><div className="flex border border-[var(--line)] bg-white p-0.5"><button className={cn("focus-ring grid h-9 w-9 place-items-center", view === "grid" && "bg-[var(--maroon)] text-white")} onClick={() => setView("grid")} title="Grid view" aria-label="Grid view"><Grid2X2 className="h-4 w-4" /></button><button className={cn("focus-ring grid h-9 w-9 place-items-center", view === "list" && "bg-[var(--maroon)] text-white")} onClick={() => setView("list")} title="List view" aria-label="List view"><List className="h-4 w-4" /></button></div></div></div>
    <div className="mt-7 grid gap-7 lg:grid-cols-[17rem_minmax(0,1fr)]"><div className={cn(!filtersOpen && "hidden lg:block")}><FilterSidebar filters={filters} categories={categories} sources={sources} years={years} onChange={updateFilter} onClear={clearAll} /></div><div>{visible.length === 0 ? <EmptyState title="No articles match these filters" description="Try a broader search or clear the active filters. Irrelevant and pending-review records remain available in the repository." /> : view === "grid" ? <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{visible.map((article) => <ArticleCard key={`${article.article_id}-${article.food_keyword}`} article={article} />)}</div> : <ArticleTable articles={visible} />}
      {filtered.length > PAGE_SIZE && <nav className="mt-8 flex items-center justify-between border-t border-[var(--line)] pt-5" aria-label="Article pagination"><Button variant="secondary" size="sm" disabled={page === 1} onClick={() => setPage((value) => value - 1)}><ChevronLeft className="h-4 w-4" />Previous</Button><span className="text-sm text-[var(--muted)]">Page {page} of {pages}</span><Button variant="secondary" size="sm" disabled={page === pages} onClick={() => setPage((value) => value + 1)}>Next<ChevronRight className="h-4 w-4" /></Button></nav>}</div></div></div>;
}
