import type { Metadata } from "next";
import { GeographyDashboard } from "@/components/geography-dashboard";
import { PageIntro } from "@/components/research-ui";
import { getArticles, toArticleSummaries } from "@/lib/data-loader";

export const metadata: Metadata = { title: "Geography" };
export default function GeographyPage() { const articles = getArticles(); return <><PageIntro eyebrow="Geography" title="Map validated incident locations" description="The geography view is prepared for state, city and coordinate data. It remains intentionally empty until location extraction and manual validation are complete." aside={<p>Location inference from headlines is disabled. This protects the map from silently converting publisher datelines or contextual place names into incident locations.</p>} /><div className="section-shell py-12"><GeographyDashboard articles={toArticleSummaries(articles)} /></div></>; }
