import {
  Activity,
  Binary,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  FileSearch,
  Network,
  Scale,
} from "lucide-react";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { LimitationsPanel, PageIntro, SectionHeading } from "@/components/research-ui";
import { formatPercent } from "@/lib/utils";

export const metadata: Metadata = { title: "Methodology" };

const publicStages = [
  ["01", "Article collection", "Candidate news records are discovered through approved search queries and source collections. Retrieval failures and duplicate text remain in the audit trail."],
  ["02", "Text preparation", "Publisher boilerplate and malformed text are conservatively cleaned. Retained articles are split into bounded chunks with traceable article and chunk identifiers."],
  ["03", "Relevance classification", "A food-specific classifier ranks articles likely to contain useful safety evidence. This is a retrieval aid, not the final event decision."],
  ["04", "Full triplet extraction", "Qwen extracts candidates from every article chunk, followed by schema routing, semantic review, atomic correction and exact-evidence checks."],
  ["05", "Mistral adjudication", "Mistral reviews the completed Qwen triplet record and resolves which claims are supported, rejected, schema gaps or still unresolved."],
  ["06", "Qwen event assembly", "Qwen combines the full article with the adjudicated triplets, assigns the article-level event label and builds grounded or ungrounded event objects."],
  ["07", "Interactive repository", "The website exposes source text, classifier metadata, model decisions, structured event fields, exact evidence and triplet audit trails."],
] as const;

const tripletStages = [
  ["A", "Qwen candidate extraction", "Every cleaned chunk is sent through the full FFLO-style extraction prompt. Each candidate retains its subject, predicate, object, entity types, confidence, evidence span and source identifiers."],
  ["B", "Deterministic schema routing", "Code checks entity types, predicates and permitted subject-object combinations, then routes schema-valid, invalid, mismatched and zero-triplet outputs."],
  ["C", "Qwen semantic review", "A separate Qwen pass tests entailment, relation direction, relation choice, entity types and whether a zero-triplet chunk missed a relation."],
  ["D", "Atomic correction and recheck", "Repairable claims are rewritten one at a time. Corrected triplets must pass structure, exact contiguous evidence and a second semantic review."],
  ["E", "Mistral adjudication", "After every Qwen triplet stage finishes, Mistral adjudicates the accepted, corrected, schema-gap and unresolved candidates. Unsupported claims are rejected; uncertain claims remain explicitly unresolved."],
] as const;

const eventStages = [
  ["A", "Lock the evidence inputs", "Qwen receives the complete cleaned article and the Mistral-adjudicated triplet record. Article and triplet identifiers are preserved."],
  ["B", "Assign the event decision", "Qwen assigns relevant_event, irrelevant or unclear. Claim status remains separate, so an alleged or suspected event is not presented as confirmed."],
  ["C", "Assemble the event object", "For event-bearing articles, Qwen structures the food, adulterants or issues, place, date, quantities, authorities, actions, laboratory context and exact evidence quotations."],
  ["D", "Separate grounded events", "An event is grounded when its material fields are supported by adjudicated triplets and traceable article evidence. Supporting identifiers and quotations stay attached."],
  ["E", "Retain ungrounded events distinctly", "If an article supports an event but material fields cannot be linked to adjudicated triplets, the event remains visibly ungrounded and separate from grounded evidence."],
] as const;

export default function MethodologyPage() {
  return (
    <>
      <PageIntro
        eyebrow="Methodology"
        title="From article discovery to evidence-grounded events"
        description="The news pipeline separates retrieval, food-specific relevance scoring, full Qwen triplet extraction, Mistral adjudication and Qwen event assembly. Each result remains traceable to its source article and evidence."
      />
      <div className="section-shell py-14">
        <SectionHeading eyebrow="Public workflow" title="Seven stages in the news pipeline" description="The implemented evidence flow from article collection to the public repository." />
        <div className="mt-8">{publicStages.map(([number, title, description]) => <PipelineStep key={number} number={number} title={title}>{description}</PipelineStep>)}</div>

        <section className="mt-20">
          <SectionHeading eyebrow="Classifier foundation" title="Food-specific relevance models" description="These are evaluation results. Classifier scores rank articles for review; they do not replace the later event decision." />
          <ClassifierPanel open food="Oil" title="Edible-oil relevance model" corpus="486-record evaluation corpus" description="Five-fold stratified cross-validation on the cleaned edible-oil corpus." results={[["F1", .836], ["Precision", .868], ["Recall", .806], ["ROC-AUC", .942], ["PR-AUC", .899]]}>
            <div className="grid gap-6 lg:grid-cols-3"><ModelComponent icon={Binary} title="TF-IDF Linear SVM" weight="0.17">Full-article lexical evidence.</ModelComponent><ModelComponent icon={Activity} title="BGE-large RBF-SVM" weight="0.67">Oil-window embeddings centred on edible-oil mentions.</ModelComponent><ModelComponent icon={BrainCircuit} title="RoBERTa-base" weight="0.17">Transformer classification using the article lead.</ModelComponent></div>
          </ClassifierPanel>
          <ClassifierPanel food="Ghee" title="Ghee relevance model" corpus="187 unique article texts" description="Five-fold out-of-fold development evaluation after exact-text deduplication: 129 relevant and 58 irrelevant articles." results={[["F1", .894], ["Precision", .905], ["Recall", .884], ["ROC-AUC", .895], ["PR-AUC", .952]]}>
            <div className="grid gap-6 lg:grid-cols-2"><ModelComponent icon={Binary} title="TF-IDF Linear SVM" weight="0.375">Calibrated lexical model using the full article.</ModelComponent><ModelComponent icon={Activity} title="MiniLM RBF-SVM" weight="0.625">Ghee-window embeddings anchored on “ghee” and “clarified butter”.</ModelComponent></div>
            <p className="mt-5 text-sm leading-6 text-[var(--muted)]">This development estimate uses the same corpus for model and weight selection; a future untouched test set is still needed.</p>
          </ClassifierPanel>
          <ClassifierPanel food="Milk" title="Milk relevance model" corpus="1,384-record evaluation corpus" description="Five-fold out-of-fold evaluation. The best F1 result is the calibrated TF-IDF Linear SVM using the title and full article body." results={[["F1", .8323], ["Precision", .8424], ["Recall", .8225], ["ROC-AUC", .9635], ["PR-AUC", .9118]]}>
            <div className="grid gap-6 lg:grid-cols-2"><ModelComponent icon={Binary} title="TF-IDF Linear SVM" weight="Best F1">Calibrated word unigrams and bigrams using the title and full article body.</ModelComponent><ModelComponent icon={BrainCircuit} title="Comparison branches" weight="Evaluated">Milk-window TF-IDF, MiniLM RBF-SVM and RoBERTa variants were evaluated in the same workbook.</ModelComponent></div>
            <p className="mt-5 text-sm leading-6 text-[var(--muted)]">The evaluation workbook includes the model comparison, out-of-fold predictions, false positives and false negatives. A separate deployment model was then fit on all 1,384 labelled records and now supplies per-article scores for all 196 published Milk records.</p>
          </ClassifierPanel>
        </section>

        <section className="mt-20">
          <SectionHeading eyebrow="Large-model event validation" title="Full Qwen triplet pipeline, then Mistral adjudication" description="Mistral adjudicates the evidence only after all Qwen extraction, review and correction stages have finished." />
          <div className="mt-8 grid gap-x-10 lg:grid-cols-2">{tripletStages.map(([number, title, description]) => <PipelineStep key={number} number={number} title={title}>{description}</PipelineStep>)}</div>
        </section>

        <section className="mt-20">
          <SectionHeading eyebrow="Event assembly" title="How Qwen builds grounded and ungrounded events" description="Qwen performs event extraction after Mistral adjudication. Grounding records whether structured fields trace through retained triplets to exact article evidence." />
          <div className="mt-8 grid gap-x-10 lg:grid-cols-2">{eventStages.map(([number, title, description]) => <PipelineStep key={number} number={number} title={title}>{description}</PipelineStep>)}</div>
        </section>

        <section className="mt-20"><SectionHeading eyebrow="Evaluation concepts" title="Precision, recall, soundness and completeness" /><div className="mt-7 grid gap-5 sm:grid-cols-2 lg:grid-cols-4"><Concept title="Precision" icon={CheckCircle2}>Among predicted-relevant articles, the proportion meeting the reference criteria.</Concept><Concept title="Recall" icon={FileSearch}>Among reference-relevant articles, the proportion recovered.</Concept><Concept title="Soundness" icon={Scale}>Whether a structured claim is supported by the article and adjudicated evidence.</Concept><Concept title="Completeness" icon={Network}>Whether all in-scope evidence is retrieved and represented; web discovery and model extraction cannot guarantee this.</Concept></div></section>

        <div className="mt-14"><LimitationsPanel>News reports are source claims, not independent laboratory verification. The event label records whether an in-scope event is present; claim status separately records whether it is suspected, alleged, pending, authority-reported or laboratory-confirmed. Ungrounded events remain distinct from grounded evidence.</LimitationsPanel></div>
      </div>
    </>
  );
}

function PipelineStep({ number, title, children }: { number: string; title: string; children: ReactNode }) { return <article className="grid gap-4 border-t border-[var(--line)] py-7 sm:grid-cols-[3rem_1fr]"><span className="font-editorial text-2xl text-[var(--saffron)]">{number}</span><div><h3 className="font-editorial text-2xl text-[var(--maroon-dark)]">{title}</h3><div className="mt-2 text-sm leading-6 text-[var(--muted)]">{children}</div></div></article>; }

function ClassifierPanel({ open = false, food, title, corpus, description, results, children }: { open?: boolean; food: string; title: string; corpus: string; description: string; results: ReadonlyArray<readonly [string, number]>; children: ReactNode }) { return <details open={open} className="group mt-8 border-y border-[var(--line)] bg-[var(--white)]"><summary className="focus-ring flex cursor-pointer list-none items-center justify-between gap-6 px-5 py-5 md:px-7"><div><p className="eyebrow">{food}</p><h3 className="font-editorial mt-2 text-2xl text-[var(--maroon-dark)]">{title}</h3></div><div className="flex shrink-0 items-center gap-3"><span className="hidden text-xs font-semibold text-[var(--muted)] sm:inline">{corpus}</span><ChevronDown className="h-5 w-5 text-[var(--maroon)] transition-transform group-open:rotate-180" /></div></summary><div className="border-t border-[var(--line)] px-5 py-7 md:px-7"><p className="max-w-4xl text-sm leading-6 text-[var(--muted)]">{description}</p><div className="mt-7 grid gap-px bg-[var(--line)] sm:grid-cols-2 lg:grid-cols-5">{results.map(([label, value]) => <ResultMetric key={label} label={label} value={value} />)}</div><div className="mt-7">{children}</div></div></details>; }
function ResultMetric({ label, value }: { label: string; value: number }) { return <div className="bg-[var(--white)] p-6"><p className="text-sm text-[var(--muted)]">{label}</p><p className="font-editorial mt-4 text-4xl text-[var(--maroon-dark)]">{formatPercent(value, 1)}</p></div>; }
function ModelComponent({ icon: Icon, title, weight, children }: { icon: typeof Activity; title: string; weight: string; children: ReactNode }) { return <article className="border-t-2 border-[var(--saffron)] py-6"><div className="flex items-start justify-between gap-4"><Icon className="h-5 w-5 text-[var(--maroon)]" /><span className="text-xs font-semibold text-[var(--muted)]">{weight}</span></div><h3 className="font-editorial mt-5 text-2xl text-[var(--maroon-dark)]">{title}</h3><p className="mt-3 text-sm leading-6 text-[var(--muted)]">{children}</p></article>; }
function Concept({ icon: Icon, title, children }: { icon: typeof Activity; title: string; children: ReactNode }) { return <article className="border-t-2 border-[var(--saffron)] pt-5"><Icon className="h-5 w-5 text-[var(--maroon)]" /><h3 className="font-editorial mt-4 text-2xl">{title}</h3><p className="mt-2 text-sm leading-6 text-[var(--muted)]">{children}</p></article>; }
