import type { Metadata } from "next";
import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Indian Food Safety Incident Observatory", template: "%s | Food Safety Observatory" },
  description: "A research interface for Indian food adulteration news evidence, FSSAI baselines and food ontology mapping.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" data-scroll-behavior="smooth"><body className="min-h-screen"><a href="#main-content" className="fixed left-4 top-3 z-[100] -translate-y-20 bg-[var(--maroon)] px-4 py-2 text-sm font-semibold text-white focus:translate-y-0">Skip to content</a><Header /><main id="main-content" className="min-h-[70vh]">{children}</main><Footer /></body></html>;
}
