import { CheckCircle2, CircleDashed, XCircle } from "lucide-react";

import type { RelevanceLabel } from "@/lib/types";
import { cn, formatPercent, titleCase } from "@/lib/utils";

export function StatusBadge({ label, className }: { label: RelevanceLabel | string; className?: string }) {
  const value = label.toLowerCase();
  const Icon = value === "relevant" ? CheckCircle2 : value === "irrelevant" ? XCircle : CircleDashed;
  return <span className={cn("inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold", value === "relevant" && "border-emerald-700/25 bg-emerald-50 text-emerald-800", value === "irrelevant" && "border-red-800/20 bg-red-50 text-red-800", !["relevant", "irrelevant"].includes(value) && "border-amber-800/20 bg-amber-50 text-amber-900", className)}><Icon className="h-3.5 w-3.5" aria-hidden="true" />{titleCase(label)}</span>;
}

export function ConfidenceBadge({ score }: { score?: number }) {
  if (score === undefined) return <span className="text-sm text-[var(--muted)]">Not available</span>;
  const level = score >= .8 ? "High" : score >= .6 ? "Moderate" : "Low";
  return <span className="inline-flex rounded-full border border-[var(--line)] bg-white px-2.5 py-1 text-xs font-semibold">{level} · {formatPercent(score, 0)}</span>;
}
