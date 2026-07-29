import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export interface ExplorerFilters { category: string; relevance: string; source: string; year: string; confidence: string }

export function FilterSidebar({ filters, categories, sources, years, onChange, onClear }: { filters: ExplorerFilters; categories: string[]; sources: string[]; years: string[]; onChange: (key: keyof ExplorerFilters, value: string) => void; onClear: () => void }) {
  return (
    <aside className="border border-[var(--line)] bg-[var(--white)] p-5 lg:sticky lg:top-24 lg:self-start">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Filter repository</h2>
        <Button variant="ghost" size="icon" onClick={onClear} title="Clear all filters" aria-label="Clear all filters">
          <RotateCcw className="h-4 w-4" />
        </Button>
      </div>
      <div className="mt-5 grid gap-5">
        <div className="grid gap-2">
          <span className="text-xs font-semibold uppercase tracking-[.06em] text-[var(--muted)]">Food category</span>
          <Select value={filters.category} onValueChange={(value) => onChange("category", value)}>
            <SelectTrigger aria-label="Filter by food category"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All categories</SelectItem>
              {categories.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        <div className="grid gap-2">
          <span className="text-xs font-semibold uppercase tracking-[.06em] text-[var(--muted)]">Human review label</span>
          <Select value={filters.relevance} onValueChange={(value) => onChange("relevance", value)}>
            <SelectTrigger aria-label="Filter by human review label"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="relevant">Relevant</SelectItem>
              <SelectItem value="irrelevant">Irrelevant</SelectItem>
              <SelectItem value="pending">Pending review</SelectItem>
              <SelectItem value="all">All labels</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="grid gap-2">
          <span className="text-xs font-semibold uppercase tracking-[.06em] text-[var(--muted)]">Source</span>
          <Select value={filters.source} onValueChange={(value) => onChange("source", value)}>
            <SelectTrigger aria-label="Filter by source"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All sources</SelectItem>
              {sources.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        <div className="grid gap-2">
          <span className="text-xs font-semibold uppercase tracking-[.06em] text-[var(--muted)]">Publication year</span>
          <Select value={filters.year} onValueChange={(value) => onChange("year", value)}>
            <SelectTrigger aria-label="Filter by publication year"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All years</SelectItem>
              {years.map((value) => <SelectItem key={value} value={value}>{value}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        <div className="grid gap-2">
          <span className="text-xs font-semibold uppercase tracking-[.06em] text-[var(--muted)]">Classifier confidence</span>
          <Select value={filters.confidence} onValueChange={(value) => onChange("confidence", value)}>
            <SelectTrigger aria-label="Filter by classifier confidence"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Any or unavailable</SelectItem>
              <SelectItem value="0.5">50% and above</SelectItem>
              <SelectItem value="0.7">70% and above</SelectItem>
              <SelectItem value="0.9">90% and above</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </aside>
  );
}
