import type { Metadata } from "next";
import { PageIntro } from "@/components/research-ui";
import { TimelineDashboard } from "@/components/timeline-dashboard";
import { getArticles, getSourceAggregates, getYearAggregates } from "@/lib/data-loader";

export const metadata: Metadata = { title: "Timeline" };

export default function TimelinePage() {
  const articles = getArticles();
  const categories = [...new Set(articles.map((article) => article.food_keyword).filter((value): value is string => Boolean(value)))];
  return <><PageIntro eyebrow="Timeline" title="Publication patterns in the corpus" description="Explore article volume, human-review labels, food-category coverage and source representation over time. Charts are generated only from records with usable publication dates." aside={<p>These charts describe the assembled research corpus. They do not estimate the underlying frequency of food-safety incidents.</p>} /><div className="section-shell py-12"><TimelineDashboard years={getYearAggregates(articles)} sources={getSourceAggregates(articles)} categories={categories} /></div></>;
}
