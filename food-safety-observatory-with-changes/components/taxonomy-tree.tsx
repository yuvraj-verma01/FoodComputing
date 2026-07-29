"use client";

import { ChevronDown, ChevronRight, GitBranch } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import type { ArticleSummary, TaxonomyData, TaxonomyNode } from "@/lib/types";
import { cn, formatNumber } from "@/lib/utils";

export function TaxonomyTree({ taxonomy, articles }: { taxonomy: TaxonomyData; articles: ArticleSummary[] }) {
  const [mode, setMode] = useState<"food" | "issue">("food");
  
  // We process the flat array into a tree structure if parent_ids exist.
  // This allows the component to work with both nested JSON and flat JSON with parent_ids.
  const nodes = useMemo(() => {
    const rawNodes = mode === "food" ? taxonomy.food_categories : taxonomy.issue_categories;
    const nodeMap = new Map<string, TaxonomyNode & { children: TaxonomyNode[] }>();
    const roots: (TaxonomyNode & { children: TaxonomyNode[] })[] = [];

    // First pass: create map of all nodes with empty children arrays
    rawNodes.forEach(node => {
      nodeMap.set(node.id, { ...node, children: node.children ? [...node.children] : [] });
    });

    // Second pass: attach children to parents
    nodeMap.forEach(node => {
      if (node.parent_id && nodeMap.has(node.parent_id)) {
        nodeMap.get(node.parent_id)!.children.push(node);
      } else {
        roots.push(node);
      }
    });

    return roots;
  }, [mode, taxonomy]);

  // Find the first node's ID for the default selection
  const firstNodeId = nodes.length > 0 ? nodes[0].id : "";
  const [selectedId, setSelectedId] = useState(firstNodeId);

  // Helper to find a node by ID anywhere in the tree
  const findNode = (nodes: TaxonomyNode[], id: string): TaxonomyNode | undefined => {
    for (const node of nodes) {
      if (node.id === id) return node;
      if (node.children) {
        const found = findNode(node.children, id);
        if (found) return found;
      }
    }
    return undefined;
  };

  const selected = useMemo(() => findNode(nodes, selectedId) ?? nodes[0], [nodes, selectedId]);
  
  const related = useMemo(() => 
    mode === "food" && selected 
      ? articles.filter((article) => article.food_keyword === selected.name && article.human_label === "relevant") 
      : [], 
    [articles, mode, selected]
  );

  function changeMode(value: "food" | "issue") { 
    setMode(value); 
    const nextRaw = value === "food" ? taxonomy.food_categories : taxonomy.issue_categories; 
    setSelectedId(nextRaw[0]?.id ?? ""); 
  }

  if (!selected) return null;

  return (
    <div>
      <div className="inline-flex border border-[var(--line)] bg-white p-1" role="tablist" aria-label="Taxonomy type">
        <button role="tab" aria-selected={mode === "food"} className={cn("focus-ring min-h-10 px-4 text-sm font-semibold", mode === "food" && "bg-[var(--maroon)] text-white")} onClick={() => changeMode("food")}>Food categories</button>
        <button role="tab" aria-selected={mode === "issue"} className={cn("focus-ring min-h-10 px-4 text-sm font-semibold", mode === "issue" && "bg-[var(--maroon)] text-white")} onClick={() => changeMode("issue")}>Issue categories</button>
      </div>
      <div className="mt-7 grid gap-7 lg:grid-cols-[20rem_minmax(0,1fr)]">
        <nav className="border border-[var(--line)] bg-[var(--white)] max-h-[800px] overflow-y-auto scrollbar-thin" aria-label={`${mode} taxonomy nodes`}>
          <div className="sticky top-0 z-10 border-b border-[var(--line)] bg-[var(--white)] p-5">
            <p className="flex items-center gap-2 text-sm font-semibold">
              <GitBranch className="h-4 w-4 text-[var(--saffron)]" />
              Provisional hierarchy
            </p>
          </div>
          <div className="flex flex-col">
            {nodes.map((node) => (
              <TreeNode 
                key={node.id} 
                node={node} 
                selectedId={selectedId} 
                onSelect={setSelectedId} 
              />
            ))}
          </div>
        </nav>
        <article className="border border-[var(--line)] bg-[var(--white)]">
          <div className="border-b border-[var(--line)] p-6 md:p-8">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-amber-800/25 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-900">
                Provisional interface taxonomy
              </span>
              <code className="text-xs text-[var(--muted)]">{selected.id}</code>
            </div>
            <h2 className="font-editorial mt-5 text-4xl text-[var(--maroon-dark)]">{selected.name}</h2>
            <p className="mt-4 max-w-3xl leading-7 text-[var(--muted)]">{selected.definition}</p>
          </div>
          <div className="grid gap-px bg-[var(--line)] sm:grid-cols-3">
            <TaxonomyMetric label="Parent category" value={selected.parent_id ?? "Top level"} />
            <TaxonomyMetric label="Child categories" value={selected.children?.length ? formatNumber(selected.children.length) : "None supplied"} />
            <TaxonomyMetric label="Incident count" value={mode === "food" ? formatNumber(related.length) : "Extraction pending"} />
          </div>
          <div className="grid gap-8 p-6 md:grid-cols-2 md:p-8">
            <div>
              <h3 className="text-sm font-semibold">Related articles</h3>
              {related.length ? (
                <ul className="mt-4 grid gap-3 text-sm">
                  {related.slice(0, 5).map((article) => (
                    <li key={article.article_id}>
                      <Link className="focus-ring text-[var(--maroon)] hover:underline" href={`/incidents/${article.slug}`}>
                        {article.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm italic text-[var(--muted)]">No validated ontology-linked articles yet.</p>
              )}
            </div>
            <div>
              <h3 className="text-sm font-semibold">FSSAI relationship</h3>
              <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{selected.fssai_relationship ?? "Not yet mapped"}</p>
              <h3 className="mt-7 text-sm font-semibold">Ontology identifier</h3>
              <p className="mt-3 text-sm italic text-[var(--muted)]">{taxonomy.status === "validated" ? selected.id : "Validated ontology identifier not yet supplied"}</p>
            </div>
          </div>
        </article>
      </div>
    </div>
  );
}

function TreeNode({ node, selectedId, onSelect, level = 0 }: { node: TaxonomyNode; selectedId: string; onSelect: (id: string) => void; level?: number }) {
  const hasChildren = node.children && node.children.length > 0;
  const isSelected = selectedId === node.id;
  const [expanded, setExpanded] = useState(level < 1 || isSelected);

  // Auto-expand if a child becomes selected
  const hasSelectedDescendant = useMemo(() => {
    const search = (n: TaxonomyNode): boolean => {
      if (n.id === selectedId) return true;
      if (n.children) return n.children.some(search);
      return false;
    };
    return hasChildren && node.children!.some(search);
  }, [hasChildren, node, selectedId]);

  if (hasSelectedDescendant && !expanded) {
    setExpanded(true);
  }

  return (
    <div className="flex flex-col border-b border-[var(--line)] last:border-0">
      <button
        onClick={() => {
          onSelect(node.id);
          if (hasChildren) setExpanded(!expanded);
        }}
        style={{ paddingLeft: `${1.25 + level * 1.5}rem` }}
        className={cn(
          "focus-ring flex w-full items-center py-3.5 pr-5 text-left text-sm transition-colors hover:bg-[var(--paper-deep)]",
          isSelected && "bg-[var(--maroon)] text-white hover:bg-[var(--maroon)]"
        )}
      >
        {hasChildren ? (
          expanded ? (
            <ChevronDown className="mr-2 h-4 w-4 shrink-0" />
          ) : (
            <ChevronRight className="mr-2 h-4 w-4 shrink-0" />
          )
        ) : (
          <span className="mr-2 h-4 w-4 shrink-0" /> // Indent spacer for leaves
        )}
        <span className="truncate">{node.name}</span>
      </button>
      
      {/* Recursively render children if expanded */}
      {hasChildren && expanded && (
        <div className="flex flex-col border-t border-[var(--line)] bg-[var(--white)]/50">
          {node.children!.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              selectedId={selectedId}
              onSelect={onSelect}
              level={level + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function TaxonomyMetric({ label, value }: { label: string; value: string }) { 
  return (
    <div className="bg-[var(--paper-deep)] p-5">
      <p className="text-xs font-semibold uppercase tracking-[.06em] text-[var(--muted)]">{label}</p>
      <p className="mt-2 text-sm font-semibold">{value}</p>
    </div>
  ); 
}
