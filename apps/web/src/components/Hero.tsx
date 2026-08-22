import { Clock, LayoutGrid, Play } from "lucide-react";

import type { Health } from "../lib/api";

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col items-center gap-1">
      <span className="font-mono text-2xl font-bold">{value}</span>
      <span className="text-[0.7rem] font-medium uppercase tracking-wider text-muted">
        {label}
      </span>
    </div>
  );
}

export default function Hero({ health }: { health: Health | null }) {
  const ativas = health ? String(health.active_automations.length) : "—";
  const timeout = health ? `${health.limits.run_timeout_s}s` : "—";

  return (
    <section
      id="topo"
      className="relative overflow-hidden pt-36 pb-20 text-center"
    >
      <div className="pointer-events-none absolute left-1/2 top-1/2 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 bg-[radial-gradient(circle,_rgba(240,177,0,0.06)_0%,_transparent_70%)]" />

      <div className="container-page relative z-10 mx-auto max-w-3xl">
        <div className="mb-6 inline-flex items-center gap-1.5 rounded-full border border-signal/20 bg-signal/10 px-3.5 py-1.5 text-xs font-semibold text-signal">
          <Clock className="h-3.5 w-3.5" />
          Execução em tempo real
        </div>

        <h1 className="mb-4 text-4xl font-extrabold leading-[1.1] tracking-tight sm:text-5xl lg:text-[3.5rem]">
          AutoTarefas{" "}
          <span className="bg-gradient-to-r from-signal to-amber-300 bg-clip-text text-transparent">
            Live System
          </span>
        </h1>

        <p className="mb-4 text-lg font-medium text-muted sm:text-xl">
          Robô de automação operacional em sandbox seguro
        </p>

        <p className="mx-auto mb-8 max-w-xl text-sm leading-relaxed text-muted/80 sm:text-base">
          Execute automações reais direto pelo navegador — sem instalar nada.
          Validação de dados, backup, scraping, integração via API e mais. Tudo
          em ambiente isolado, com execução real, stdout via terminal e
          artefatos para download.
        </p>

        <div className="mb-12 flex flex-col justify-center gap-3 sm:flex-row">
          <a
            href="#execucao"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-signal px-5 py-2.5 text-sm font-semibold text-black shadow-[0_0_20px_rgba(240,177,0,0.2)] transition-all hover:bg-amber-400 hover:shadow-[0_0_30px_rgba(240,177,0,0.3)]"
          >
            <Play className="h-4 w-4 fill-current" />
            Executar automação
          </a>
          <a
            href="#catalogo"
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/10 bg-surface px-5 py-2.5 text-sm font-medium text-fg transition-colors hover:bg-surface-2"
          >
            <LayoutGrid className="h-4 w-4" />
            Ver catálogo
          </a>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-6 sm:gap-10">
          <Metric value={ativas} label="Automações ativas" />
          <div className="hidden h-10 w-px bg-white/[0.06] sm:block" />
          <Metric value={timeout} label="Timeout por execução" />
          <div className="hidden h-10 w-px bg-white/[0.06] sm:block" />
          <Metric value="100%" label="Sandbox isolado" />
        </div>
      </div>
    </section>
  );
}
