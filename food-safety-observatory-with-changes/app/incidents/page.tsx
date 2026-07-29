import type { Metadata } from "next";
import { IncidentExplorer } from "@/components/incident-explorer";
import { DemoBanner, PageIntro } from "@/components/research-ui";
import { getArticles, getDataProfile, toArticleSummaries } from "@/lib/data-loader";

export const metadata: Metadata = { title: "Incident Explorer" };

export default function IncidentsPage() {
  const articles = getArticles();
  const profile = getDataProfile(articles);
  return <>{profile.isDemo && <DemoBanner />}<PageIntro eyebrow="Incident explorer" title="Search the research corpus" description="Browse relevant, irrelevant and pending-review news records. Human labels and trained-classifier outputs are shown separately so the repository remains an auditable research record." aside={<p>The default view shows human-reviewed relevant articles. Use the label filter to inspect rejected records or the unreviewed ghee queue.</p>} /><IncidentExplorer articles={toArticleSummaries(articles)} /></>;
}
