import type { Metadata } from "next";
import { PageIntro } from "@/components/research-ui";
import { TaxonomyTree } from "@/components/taxonomy-tree";
import { getArticles, getTaxonomy, toArticleSummaries } from "@/lib/data-loader";

export const metadata: Metadata = { title: "Food & Issue Taxonomy" };
export default function TaxonomyPage() { const articles = getArticles(); return <><PageIntro eyebrow="Food & issue taxonomy" title="A shared vocabulary for incident evidence" description="Browse the provisional interface categories that will later be replaced or enriched by the validated Indian food ontology." aside={<p>These categories organise the interface only. They are not presented as a completed ontology or official FSSAI classification.</p>} /><div className="section-shell py-12"><TaxonomyTree taxonomy={getTaxonomy()} articles={toArticleSummaries(articles)} /></div></>; }
