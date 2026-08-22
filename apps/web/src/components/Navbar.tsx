import { CheckSquare } from "lucide-react";

const LINKS: [string, string][] = [
  ["Catálogo", "#catalogo"],
  ["Execução", "#execucao"],
  ["Terminal", "#terminal"],
  ["Artefatos", "#artefatos"],
];

export default function Navbar({ online }: { online: boolean }) {
  return (
    <nav className="fixed inset-x-0 top-0 z-50 border-b border-white/[0.06] bg-ink/85 backdrop-blur-xl">
      <div className="container-page flex h-16 items-center justify-between">
        <a href="#topo" className="flex items-center gap-2.5">
          <CheckSquare className="h-5 w-5 text-signal" />
          <span className="text-[1.05rem] font-bold tracking-tight">
            AutoTarefas
          </span>
          <span className="rounded bg-signal px-1.5 py-0.5 text-[0.6rem] font-bold tracking-wider text-black">
            LIVE
          </span>
        </a>

        <div className="hidden items-center gap-8 md:flex">
          {LINKS.map(([label, href]) => (
            <a
              key={href}
              href={href}
              className="text-sm font-medium text-muted transition-colors hover:text-fg"
            >
              {label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${online ? "animate-pulse-dot bg-ok" : "bg-muted"}`}
            aria-hidden
          />
          <span className="hidden text-xs font-medium text-muted sm:inline">
            {online ? "Sistema operacional" : "Conectando…"}
          </span>
        </div>
      </div>
    </nav>
  );
}
