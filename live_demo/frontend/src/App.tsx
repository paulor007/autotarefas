import { useEffect, useState } from "react";

import CatalogGrid from "./components/CatalogGrid";
import HealthBar from "./components/HealthBar";
import { getCatalog, getHealth, type Catalog, type Health } from "./lib/api";

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; health: Health; catalog: Catalog };

export default function App() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    Promise.all([getHealth(), getCatalog()])
      .then(([health, catalog]) => {
        if (!cancelled) {
          setState({ phase: "ready", health, catalog });
        }
      })
      .catch((error: unknown) => {
        const message =
          error instanceof Error ? error.message : "falha ao carregar";
        if (!cancelled) {
          setState({ phase: "error", message });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen">
      <div className="mx-auto w-full max-w-6xl px-6 py-10 sm:py-14">
        <header className="mb-10">
          <p className="mb-3 font-mono text-xs uppercase tracking-[0.22em] text-signal">
            sandbox seguro · execução real
          </p>
          <h1 className="font-display text-4xl font-bold tracking-tight text-text sm:text-5xl">
            AutoTarefas
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-relaxed text-text-muted">
            Robô de automação operacional. Aqui você roda as tarefas de verdade
            — num ambiente isolado, sem instalar nada. O catálogo abaixo é
            executado pelo backend real; nas próximas etapas você acompanha o
            stdout ao vivo e baixa os artefatos gerados.
          </p>
        </header>

        {state.phase === "ready" && (
          <>
            <div className="mb-12 animate-fade-up">
              <HealthBar health={state.health} />
            </div>
            <div className="animate-fade-up">
              <CatalogGrid
                catalog={state.catalog}
                activeIds={new Set(state.health.active_automations)}
              />
            </div>
          </>
        )}

        {state.phase === "loading" && (
          <div className="flex items-center gap-3 font-mono text-sm text-text-muted">
            <span className="h-2 w-2 animate-pulse-dot rounded-full bg-cyan" />
            carregando catálogo do backend…
          </div>
        )}

        {state.phase === "error" && (
          <div className="rounded-lg border border-warn/40 bg-warn/5 px-5 py-4">
            <p className="font-mono text-sm text-warn">
              não foi possível falar com o backend
            </p>
            <p className="mt-1 text-sm text-text-muted">
              {state.message}. Confirme que o servidor está no ar em{" "}
              <code className="font-mono text-text-dim">localhost:7860</code> e
              recarregue.
            </p>
          </div>
        )}

        <footer className="mt-16 border-t border-line pt-6 font-mono text-xs text-text-dim">
          AutoTarefas · Live System — execução real em sandbox isolado.
        </footer>
      </div>
    </div>
  );
}
