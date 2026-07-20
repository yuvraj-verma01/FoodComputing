"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { DataAvailabilityNotice } from "@/components/research-ui";
import type { ArticleSummary } from "@/lib/types";

const IndiaMap = dynamic(() => import("@/components/india-map").then((module) => module.IndiaMap), { ssr: false, loading: () => <div className="min-h-[520px] animate-pulse bg-[var(--paper-deep)]" /> });

export function GeographyDashboard({ articles }: { articles: ArticleSummary[] }) {
  const [selected, setSelected] = useState<string | null>(null);
  const located = articles.filter((article) => article.location_state);
  const coverage = articles.length ? located.length / articles.length : 0;
  const states = useMemo(() => {
    const counts = new Map<string, number>();
    located.forEach((article) => counts.set(article.location_state!, (counts.get(article.location_state!) ?? 0) + 1));
    return [...counts].map(([state, total]) => ({ state, total })).sort((a, b) => b.total - a.total);
  }, [located]);

  return <div className="grid gap-7 lg:grid-cols-[minmax(0,1fr)_21rem]"><div className="relative min-h-[520px] overflow-hidden border border-[var(--line)] bg-[var(--paper-deep)]"><IndiaMap articles={articles} />{located.length === 0 && <div className="absolute inset-0 z-[500] grid place-items-center bg-[var(--paper)]/80 p-6 backdrop-blur-[2px]"><div className="w-full max-w-xl"><DataAvailabilityNotice title="Geographic incident mapping will become available after location extraction and validation." progress={coverage}>No locations are inferred from article titles. Only validated <code>location_state</code> values or supplied coordinates will be mapped.</DataAvailabilityNotice></div></div>}</div><aside>{states.length ? <div className="border border-[var(--line)] bg-[var(--white)]"><div className="border-b border-[var(--line)] p-5"><h2 className="font-editorial text-2xl">Ranked states</h2><p className="mt-1 text-xs text-[var(--muted)]">Select a state to focus its records.</p></div><div className="max-h-[520px] overflow-auto">{states.map((item, index) => <button key={item.state} className="focus-ring flex w-full items-center justify-between border-b border-[var(--line)] px-5 py-4 text-left text-sm hover:bg-[var(--paper-deep)]" onClick={() => setSelected(item.state)}><span><span className="mr-3 text-[var(--muted)]">{index + 1}</span>{item.state}</span><strong>{item.total}</strong></button>)}</div>{selected && <p className="p-4 text-xs text-[var(--muted)]">Selected: {selected}</p>}</div> : <div className="border border-[var(--line)] bg-[var(--white)] p-5"><h2 className="font-editorial text-2xl">Ranked states</h2><p className="mt-3 text-sm leading-6 text-[var(--muted)]">No validated state values are loaded. This table will populate automatically after extraction.</p></div>}</aside></div>;
}
