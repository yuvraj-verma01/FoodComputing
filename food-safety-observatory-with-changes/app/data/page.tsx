import { Download, FileJson, FileSpreadsheet } from "lucide-react";

import { Button } from "@/components/ui/button";

const datasets = [
  {
    name: "articles.csv",
    description: "The active website corpus containing all processed incident records, text, and classifier predictions.",
    icon: FileSpreadsheet,
    size: "CSV",
  },
  {
    name: "articles.sample.csv",
    description: "Clearly labelled interface-only demonstration records used for testing UI state.",
    icon: FileSpreadsheet,
    size: "CSV",
  },
  {
    name: "current-data-report.json",
    description: "Summary of the generated project export, showing counts and quality metrics.",
    icon: FileJson,
    size: "JSON",
  },
  {
    name: "taxonomy.json",
    description: "The provisional food and issue taxonomy used for hierarchical filtering.",
    icon: FileJson,
    size: "JSON",
  },
];

export default function DataDownloadPage() {
  return (
    <div className="section-shell py-12 md:py-16">
      <div className="max-w-3xl">
        <h1 className="font-editorial text-4xl font-bold tracking-tight text-[var(--maroon-dark)] sm:text-5xl">
          Data Export
        </h1>
        <p className="mt-6 text-lg leading-relaxed text-[var(--muted)]">
          Download the raw data files powering the Indian Food Safety Incident Observatory.
          The master corpus, interface samples, and configuration JSONs are available here.
        </p>
      </div>

      <div className="mt-12 grid gap-6 md:grid-cols-2">
        {datasets.map((file) => (
          <div
            key={file.name}
            className="flex flex-col rounded-lg border border-[var(--line)] bg-[var(--white)] p-6 transition-shadow hover:shadow-md"
          >
            <div className="flex items-start gap-4">
              <div className="grid h-12 w-12 shrink-0 place-items-center rounded bg-[var(--paper-deep)] text-[var(--maroon)]">
                <file.icon className="h-6 w-6" />
              </div>
              <div className="flex-1 space-y-1">
                <h3 className="font-semibold text-[var(--ink)]">{file.name}</h3>
                <p className="text-sm text-[var(--muted)]">{file.description}</p>
              </div>
            </div>
            <div className="mt-6 flex items-center justify-between border-t border-[var(--line)] pt-4">
              <span className="text-xs font-semibold uppercase tracking-[.06em] text-[var(--muted)]">
                Format: {file.size}
              </span>
              <Button asChild size="sm" className="gap-2">
                <a href={`/api/download?file=${file.name}`} download={file.name}>
                  <Download className="h-4 w-4" /> Download
                </a>
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
