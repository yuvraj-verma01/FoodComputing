import type { Metadata } from "next";
import { FSSAIComparisonCard, PageIntro, SectionHeading } from "@/components/research-ui";
import { getFssaiBaselines } from "@/lib/data-loader";

export const metadata: Metadata = { title: "FSSAI Baseline" };
const framework = [
  ["Alignment", "A news issue directly corresponds to a parameter explicitly tested in the relevant FSSAI survey."],
  ["Divergence", "News evidence and the structured survey appear to indicate different patterns after scope and time are made comparable."],
  ["Scope Gap", "A news-reported issue was not tested or was not explicitly covered by that survey."],
];

export default function FssaiBaselinePage() { const baselines = getFssaiBaselines(); return <><PageIntro eyebrow="FSSAI baseline" title="Compare incident reports with official survey scope" description="FSSAI survey reports provide laboratory-tested baselines. The Observatory will compare them with news evidence without treating unlike methods or scopes as directly equivalent." aside={<p>No numerical FSSAI findings are shown until validated source data are supplied to the project.</p>} /><div className="section-shell py-14"><div className="grid gap-7">{baselines.map((baseline) => <FSSAIComparisonCard baseline={baseline} key={baseline.id} />)}</div><section className="mt-16"><SectionHeading eyebrow="Comparison framework" title="Three outcomes, kept analytically distinct" description="Future comparison records will require a documented survey parameter, compatible unit of analysis and validated news extraction." /><div className="mt-8 grid gap-px bg-[var(--line)] md:grid-cols-3">{framework.map(([title, description], index) => <article className="bg-[var(--white)] p-6" key={title}><p className="font-editorial text-4xl text-[var(--saffron)]">0{index + 1}</p><h3 className="font-editorial mt-5 text-2xl text-[var(--maroon-dark)]">{title}</h3><p className="mt-3 text-sm leading-6 text-[var(--muted)]">{description}</p><p className="mt-6 text-xs font-semibold uppercase tracking-[.06em] text-[var(--muted)]">No comparison records loaded</p></article>)}</div></section></div></>; }
