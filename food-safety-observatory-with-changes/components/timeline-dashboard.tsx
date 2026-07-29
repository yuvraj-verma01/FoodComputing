"use client";

import type { ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DataAvailabilityNotice } from "@/components/research-ui";
import type { SourceAggregate, YearAggregate } from "@/lib/types";

const colors = { maroon: "#761c2f", saffron: "#c27b24", sage: "#557063", grey: "#a8a198", ghee: "#8d6d31" };

export function ChartContainer({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return <section className="border border-[var(--line)] bg-[var(--white)] p-5 md:p-7"><h2 className="font-editorial text-2xl text-[var(--maroon-dark)]">{title}</h2><p className="mt-2 text-sm leading-6 text-[var(--muted)]">{description}</p><div className="mt-7 h-[320px] w-full">{children}</div></section>;
}

const tooltipStyle = { background: "#fffdf8", border: "1px solid #d8d0c4", borderRadius: 0, fontSize: 12 };

export function TimelineDashboard({ years, sources, categories }: { years: YearAggregate[]; sources: SourceAggregate[]; categories: string[] }) {
  if (!years.length) return <DataAvailabilityNotice title="Publication dates are unavailable">Timeline charts will appear when usable article dates are loaded.</DataAvailabilityNotice>;
  return <div className="grid gap-6 lg:grid-cols-2"><ChartContainer title="Articles by publication year" description="All corpus records with a valid publication date."><ResponsiveContainer width="100%" height="100%"><BarChart data={years} margin={{ left: -18, right: 8 }}><CartesianGrid stroke="#e5ded3" vertical={false} /><XAxis dataKey="year" tick={{ fontSize: 12 }} /><YAxis allowDecimals={false} tick={{ fontSize: 12 }} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey="total" name="Articles" fill={colors.maroon} /></BarChart></ResponsiveContainer></ChartContainer>
    <ChartContainer title="Human labels over time" description="Relevant, irrelevant and pending-review records by publication year."><ResponsiveContainer width="100%" height="100%"><LineChart data={years} margin={{ left: -18, right: 12 }}><CartesianGrid stroke="#e5ded3" vertical={false} /><XAxis dataKey="year" tick={{ fontSize: 12 }} /><YAxis allowDecimals={false} tick={{ fontSize: 12 }} /><Tooltip contentStyle={tooltipStyle} /><Legend /><Line type="monotone" dataKey="relevant" stroke={colors.sage} strokeWidth={2} dot={false} /><Line type="monotone" dataKey="irrelevant" stroke={colors.maroon} strokeWidth={2} dot={false} /><Line type="monotone" dataKey="pending" stroke={colors.saffron} strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></ChartContainer>
    <ChartContainer title="Food-category coverage" description="Corpus composition over time. Counts reflect collection and labelling coverage, not incidence rates."><ResponsiveContainer width="100%" height="100%"><BarChart data={years} margin={{ left: -18, right: 8 }}><CartesianGrid stroke="#e5ded3" vertical={false} /><XAxis dataKey="year" tick={{ fontSize: 12 }} /><YAxis allowDecimals={false} tick={{ fontSize: 12 }} /><Tooltip contentStyle={tooltipStyle} /><Legend />{categories.map((category, index) => <Bar key={category} dataKey={category} stackId="food" fill={index === 0 ? colors.maroon : index === 1 ? colors.ghee : colors.saffron} />)}</BarChart></ResponsiveContainer></ChartContainer>
    <ChartContainer title="Most represented publications" description="Top ten sources in the loaded corpus; this is a coverage view rather than a measure of publisher activity."><ResponsiveContainer width="100%" height="100%"><BarChart data={sources.slice(0, 10)} layout="vertical" margin={{ left: 38, right: 8 }}><CartesianGrid stroke="#e5ded3" horizontal={false} /><XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} /><YAxis type="category" dataKey="source" width={115} tick={{ fontSize: 11 }} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey="total" name="Articles" fill={colors.saffron} /></BarChart></ResponsiveContainer></ChartContainer></div>;
}
