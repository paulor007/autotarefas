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
}: Props) {
  const automations: Automation[] = catalog?.automations ?? [];
  const active = automations.filter((a) => activeIds.has(a.id));
  const soon = automations.filter((a) => !activeIds.has(a.id));

  return (
    <section id="catalogo" className="py-20">
      <div className="container-page">
        <SectionHeader
          title="Catálogo de Automações"
          subtitle="Selecione uma automação para executar no ambiente sandbox"
        />

        {loading && (
          <div className="flex items-center justify-center gap-3 font-mono text-sm text-muted">
            <span className="h-2 w-2 animate-pulse-dot rounded-full bg-cyan" />
            carregando catálogo do backend…
          </div>
        )}

        {error && !loading && (
          <div className="mx-auto max-w-lg rounded-lg border border-danger/40 bg-danger/5 px-5 py-4 text-center">
            <p className="font-mono text-sm text-danger">
              não foi possível carregar o catálogo
            </p>
            <p className="mt-1 text-sm text-muted">
              {error}. Confirme que o backend está em{" "}
              <code className="font-mono">localhost:7860</code>.
            </p>
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
