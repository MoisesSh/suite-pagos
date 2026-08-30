import { codeToHtml } from "shiki";

interface CodeBlockProps {
  code: string;
  lang: string;
  filename?: string;
}

// Highlighting server-side (Server Component): cero JS de sintaxis en el
// cliente. Tema oscuro fijo a propósito, independiente del tema de la
// página (este portal no tiene toggle claro/oscuro todavía) — mismo patrón
// que la mayoría de sitios de documentación de API (Stripe, Twilio).
export default async function CodeBlock({ code, lang, filename }: CodeBlockProps) {
  const html = await codeToHtml(code.trim(), { lang, theme: "dark-plus" });

  return (
    <div className="overflow-hidden rounded-lg border border-zinc-800 text-sm">
      {filename && (
        <div className="border-b border-white/10 bg-zinc-900 px-4 py-1.5 font-mono text-xs text-zinc-400">
          {filename}
        </div>
      )}
      <div
        className="[&_pre]:overflow-x-auto [&_pre]:p-4 [&_pre]:leading-relaxed"
        // shiki produce HTML estático y confiable (contenido literal de esta
        // misma codebase, nunca input de usuario) — dangerouslySetInnerHTML
        // es el mecanismo documentado por shiki para esto.
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
