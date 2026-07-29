import { ArrowRight, Check, CircleDashed, Clock3 } from "lucide-react";
import { cn } from "@/lib/utils";

const steps = [
  ["Article Collection", "complete"], ["Text Cleaning", "complete"],
  ["Relevance Classification", "complete"], ["Large-model Event Validation", "planned"],
  ["Entity Extraction", "progress"], ["Ontology Mapping", "planned"],
  ["FSSAI Comparison", "planned"], ["Interactive Repository", "complete"],
] as const;

export function PipelineDiagram() {
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{steps.map(([label, status], index) => { const Icon = status === "complete" ? Check : status === "progress" ? Clock3 : CircleDashed; return <div key={label} className="relative"><div className={cn("flex min-h-28 flex-col justify-between border p-4", status === "complete" && "border-emerald-800/30 bg-emerald-50/60", status === "progress" && "border-amber-800/30 bg-amber-50/60", status === "planned" && "border-[var(--line)] bg-[var(--white)]")}><div className="flex items-center justify-between"><span className="text-xs font-semibold uppercase tracking-[.08em] text-[var(--muted)]">{String(index + 1).padStart(2, "0")}</span><Icon className="h-4 w-4" /></div><p className="mt-5 text-sm font-semibold leading-5">{label}</p></div>{index < steps.length - 1 && <ArrowRight className="absolute -right-3 top-1/2 z-10 hidden h-5 w-5 -translate-y-1/2 bg-[var(--paper)] text-[var(--saffron)] lg:block" />}</div>; })}</div>;
}
