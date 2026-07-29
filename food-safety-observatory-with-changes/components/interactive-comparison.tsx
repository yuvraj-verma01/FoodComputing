"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { cn } from "@/lib/utils";

const mockComparisonData = [
  { issue: "Water Dilution", official: 15, news: 4.5 },
  { issue: "Urea", official: 0.2, news: 12.8 },
  { issue: "Detergent", official: 0, news: 8.4 },
  { issue: "Starch", official: 2.1, news: 18.2 },
  { issue: "Aflatoxin M1", official: 5.4, news: 0.5 },
];

export function InteractiveComparison() {
  const [view, setView] = useState<"official" | "news">("official");

  // Format data so Recharts can animate the transition on the same Bar
  const chartData = mockComparisonData.map((d) => ({
    issue: d.issue,
    value: view === "official" ? d.official : d.news,
    fill: view === "official" ? "var(--saffron)" : "var(--maroon)",
  }));

  return (
    <section className="mt-16 border-t border-[var(--line)] pt-16">
      <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="eyebrow">Interactive Demonstration</p>
          <h2 className="font-editorial mt-2 text-3xl leading-tight text-[var(--maroon-dark)] md:text-4xl">
            Visualizing Divergence & Scope Gaps
          </h2>
          <p className="mt-3 max-w-2xl leading-7 text-[var(--muted)]">
            Use the toggle below to instantly compare official laboratory baseline percentages against the prevalence of those issues reported in the news corpus. (Data is mocked for demonstration).
          </p>
        </div>
      </div>

      <div className="mt-10 border border-[var(--line)] bg-[var(--white)] p-6 md:p-10">
        <div className="flex flex-col items-center justify-between gap-6 md:flex-row">
          <div>
            <h3 className="font-editorial text-2xl text-[var(--ink)]">
              {view === "official" ? "FSSAI Official Survey Results" : "News Corpus Mentions"}
            </h3>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Percentage of total samples/articles flagging this issue
            </p>
          </div>

          <div className="inline-flex rounded-[4px] border border-[var(--line)] bg-[var(--paper-deep)] p-1">
            <button
              onClick={() => setView("official")}
              className={cn(
                "focus-ring rounded-[2px] px-6 py-2 text-sm font-semibold transition-colors",
                view === "official" ? "bg-white shadow-sm" : "text-[var(--muted)] hover:text-[var(--ink)]"
              )}
            >
              Official Baseline
            </button>
            <button
              onClick={() => setView("news")}
              className={cn(
                "focus-ring rounded-[2px] px-6 py-2 text-sm font-semibold transition-colors",
                view === "news" ? "bg-white shadow-sm" : "text-[var(--muted)] hover:text-[var(--ink)]"
              )}
            >
              News Corpus
            </button>
          </div>
        </div>

        <div className="mt-12 h-[400px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--line)" />
              <XAxis 
                dataKey="issue" 
                tickLine={false} 
                axisLine={false} 
                tick={{ fill: 'var(--muted)', fontSize: 12 }} 
                dy={10} 
              />
              <YAxis 
                tickFormatter={(value) => `${value}%`} 
                tickLine={false} 
                axisLine={false} 
                tick={{ fill: 'var(--muted)', fontSize: 12 }} 
              />
              <Tooltip 
                cursor={{ fill: 'var(--paper-deep)', opacity: 0.5 }}
                contentStyle={{ borderRadius: '4px', border: '1px solid var(--line)', backgroundColor: 'var(--white)' }}
                formatter={(value: any) => [`${Number(value).toFixed(1)}%`, 'Prevalence']}
              />
              <Bar 
                dataKey="value" 
                radius={[4, 4, 0, 0]} 
                animationDuration={800}
                animationEasing="ease-in-out"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
}
