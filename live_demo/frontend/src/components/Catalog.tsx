import type { Automation, Catalog as CatalogData } from "../lib/api";
import AutomationCard from "./AutomationCard";
import SectionHeader from "./SectionHeader";

interface Props {
  catalog: CatalogData | null;
  activeIds: Set<string>;
  selectedId: string | null;
  onSelect: (id: string) => void;
  loading: boolean;
  error: string | null;
  /** Refaz a carga quando o serviço não respondeu. */
  onRetry?: () => void;
}

const GRID =
  "grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4";

export default function Catalog({
  catalog,
  activeIds,
  selectedId,
  onSelect,
  loading,
  error,
  onRetry,
}: Props) {
  const automations: Automation[] = catalog?.automations ?? [];
  const active = automations.filter((a) => activeIds.has(a.id));
  const soon = automations.filter((a) => !activeIds.has(a.id));

  return (
    <section id="catalogo" className="py-20">
      <div className="container-page">
        <SectionHeader
          title="Soluções disponíveis"
          subtitle="Escolha uma solução para executar sobre os seus dados, em ambiente isolado"
        />

        {loading && (
          <div className="flex items-center justify-center gap-3 font-mono text-sm text-muted">
            <span className="h-2 w-2 animate-pulse-dot rounded-full bg-cyan" />
            carregando catálogo do backend…
          </div>
        )}

        {error && !loading && (
          <div className="mx-auto max-w-lg rounded-lg border border-danger/40 bg-danger/5 px-5 py-4 text-center">
            <p className="text-sm font-semibold text-danger">
              Não foi possível carregar as soluções
            </p>
            {/* Sem host nem porta: essa informacao depende de como o ambiente
                foi iniciado e mudaria a cada configuracao. O detalhe tecnico
                (ECONNREFUSED, alvo do proxy) fica no console de dev, onde
                quem esta depurando consegue ver. */}
            <p className="mt-1 text-sm text-muted">
              O serviço não respondeu. Verifique se ele está em execução e tente
              novamente.
            </p>
            {onRetry ? (
              <button
                type="button"
                onClick={onRetry}
                className="mt-3 rounded-lg border border-white/12 px-4 py-2 text-sm font-semibold text-fg hover:border-white/25"
              >
                Tentar novamente
              </button>
            ) : null}
          </div>
        )}

        {!loading && !error && (
          <>
            <div className={GRID}>
              {active.map((automation) => (
                <AutomationCard
                  key={automation.id}
                  automation={automation}
                  active
                  selected={selectedId === automation.id}
                  onSelect={onSelect}
                />
              ))}
            </div>

            {soon.length > 0 && (
              <>
                <h3 className="mb-5 mt-14 text-sm font-semibold uppercase tracking-wider text-muted">
                  Em breve
                </h3>
                <div className={GRID}>
                  {soon.map((automation) => (
                    <AutomationCard
                      key={automation.id}
                      automation={automation}
                      active={false}
                      selected={false}
                      onSelect={onSelect}
                    />
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </section>
  );
}
