"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/guia", label: "Resumen y prerequisito" },
  { href: "/guia/flujo", label: "El flujo (3 pasos)" },
  { href: "/guia/webhooks", label: "Webhook server-to-server" },
  { href: "/guia/errores", label: "Errores y ambiente QA" },
] as const;

export default function GuiaSidebar() {
  const pathname = usePathname();

  return (
    <nav aria-label="Secciones de la guía de integración">
      <ul className="flex gap-1 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible lg:pb-0">
        {LINKS.map((link) => {
          const active = pathname === link.href;
          return (
            <li key={link.href} className="shrink-0 lg:shrink">
              <Link
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={`block rounded-md px-3 py-2 text-sm whitespace-nowrap transition-colors lg:whitespace-normal ${
                  active
                    ? "bg-accent font-medium text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                }`}
              >
                {link.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
