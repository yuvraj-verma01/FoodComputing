"use client";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) { return <section className="section-shell py-28"><AlertTriangle className="h-8 w-8 text-[var(--danger)]" /><h1 className="font-editorial mt-5 text-4xl">The data view could not be loaded.</h1><p className="mt-4 text-[var(--muted)]">Check that <code className="bg-white px-1.5 py-1">/data/articles.csv</code> is present and uses the documented schema.</p><Button className="mt-8" onClick={reset}>Try again</Button></section>; }
