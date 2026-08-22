import { ArrowRight } from "lucide-react";

const steps = [
  "Article Collection",
  "Text Preparation",
  "Relevance Classification",
  "Full Triplet Extraction",
  "Mistral Adjudication",
  "Qwen Event Assembly",
  "Interactive Repository",
] as const;

export function PipelineDiagram() {
  return (
    <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {steps.map((label, index) => (
        <li key={label} className="relative">
          <div className="flex min-h-28 flex-col justify-between border border-[var(--line)] bg-[var(--white)] p-4">
            <span className="text-xs font-semibold uppercase tracking-[.08em] text-[var(--saffron)]">
              {String(index + 1).padStart(2, "0")}
            </span>
            <p className="mt-5 text-sm font-semibold leading-5">{label}</p>
          </div>
          {index < steps.length - 1 && (
            <ArrowRight className="absolute -right-3 top-1/2 z-10 hidden h-5 w-5 -translate-y-1/2 bg-[var(--paper)] text-[var(--saffron)] lg:block" />
          )}
        </li>
      ))}
    </ol>
  );
}
