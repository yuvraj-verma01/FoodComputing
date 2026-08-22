"use client";

import { Menu, Microscope, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { cn } from "@/lib/utils";

const links: ReadonlyArray<{
  label: string;
  href: string;
  external?: boolean;
}> = [
  { label: "Overview", href: "/" },
  { label: "Incidents", href: "/incidents" },
  { label: "Timeline", href: "/timeline" },
  { label: "Geography", href: "/geography" },
  { label: "Food & Issue Taxonomy", href: "/taxonomy" },
  { label: "Data Export", href: "/data" },
  { label: "Methodology", href: "/methodology" },
  {
    label: "Baseline FSSAI Pipeline",
    href: "https://food-safety-observatory-with-change.vercel.app/",
    external: true,
  },
];

export function Header() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b border-[var(--line)] bg-[var(--paper)]/95 backdrop-blur">
      <div className="section-shell flex min-h-20 items-center justify-between gap-6">
        <Link
          href="/"
          className="focus-ring flex items-center gap-3"
          onClick={() => setOpen(false)}
        >
          <span className="grid h-10 w-10 place-items-center border border-[var(--maroon)] text-[var(--maroon)]">
            <Microscope className="h-5 w-5" />
          </span>
          <span className="hidden max-w-[15rem] text-sm font-semibold leading-tight text-[var(--maroon-dark)] sm:block">
            Indian Food Safety<br />Incident Observatory
          </span>
        </Link>
        <button
          className="focus-ring grid h-11 w-11 place-items-center text-[var(--maroon)] xl:hidden"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          aria-controls="site-navigation"
          aria-label={open ? "Close navigation" : "Open navigation"}
        >
          {open ? <X /> : <Menu />}
        </button>
        <nav
          id="site-navigation"
          aria-label="Primary navigation"
          className={cn(
            "absolute left-0 right-0 top-20 border-b border-[var(--line)] bg-[var(--paper)] px-4 py-4 xl:static xl:block xl:border-0 xl:bg-transparent xl:p-0",
            !open && "hidden xl:block",
          )}
        >
          <ul className="section-shell flex flex-col gap-1 xl:w-auto xl:flex-row xl:items-center xl:gap-0">
            {links.map((link) => {
              const active = !link.external && (
                link.href === "/" ? pathname === "/" : pathname.startsWith(link.href)
              );
              const className = cn(
                "focus-ring block border-b-2 border-transparent px-3 py-3 text-sm font-medium hover:text-[var(--maroon)] xl:py-7",
                active && "border-[var(--saffron)] text-[var(--maroon)]",
              );

              return (
                <li key={link.href}>
                  {link.external ? (
                    <a
                      href={link.href}
                      target="_blank"
                      rel="noreferrer"
                      onClick={() => setOpen(false)}
                      className={className}
                    >
                      {link.label}
                    </a>
                  ) : (
                    <Link
                      href={link.href}
                      onClick={() => setOpen(false)}
                      className={className}
                    >
                      {link.label}
                    </Link>
                  )}
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </header>
  );
}
