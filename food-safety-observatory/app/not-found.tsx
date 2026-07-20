import Link from "next/link";
import { Button } from "@/components/ui/button";
export default function NotFound() { return <section className="section-shell py-28"><p className="eyebrow">Record not found</p><h1 className="font-editorial mt-4 text-5xl">This research record is unavailable.</h1><p className="mt-5 max-w-xl text-[var(--muted)]">It may have been removed from the current data export or its identifier may have changed.</p><Button asChild className="mt-8"><Link href="/incidents">Return to incidents</Link></Button></section>; }
