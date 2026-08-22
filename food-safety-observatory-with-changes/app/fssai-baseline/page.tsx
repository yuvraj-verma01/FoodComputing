import type { Metadata } from "next";

import { DataAvailabilityNotice, PageIntro } from "@/components/research-ui";

export const metadata: Metadata = { title: "FSSAI Baseline" };

export default function FssaiBaselinePage() {
  return (
    <>
      <PageIntro
        eyebrow="FSSAI baseline"
        title="FSSAI baseline"
        description="Validated FSSAI baseline data and incident comparisons will appear here when they are available."
        aside={<p>No baseline records are currently available to display.</p>}
      />
      <div className="section-shell py-14 md:py-16">
        <DataAvailabilityNotice title="To be added">
          No validated FSSAI baseline data is available to publish yet.
        </DataAvailabilityNotice>
      </div>
    </>
  );
}
