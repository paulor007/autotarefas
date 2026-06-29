import { useEffect, useMemo, useState } from "react";

import Artifacts from "./components/Artifacts";
import Catalog from "./components/Catalog";
import ExecutionPanel from "./components/ExecutionPanel";
import Footer from "./components/Footer";
import Hero from "./components/Hero";
import Navbar from "./components/Navbar";
import StatusBar from "./components/StatusBar";
import TerminalView, { type TerminalLine } from "./components/TerminalView";
import {
  getCatalog,
  getHealth,
  type Catalog as CatalogData,
  type Health,
} from "./lib/api";

// Saida de exemplo: linhas reais representativas do stdout do AutoTarefas
// (validate com o clientes.csv de exemplo, ja validado no backend). No Front-2,
// este terminal passa a consumir o SSE real de /api/stream/{token}.
const SAMPLE_LINES: TerminalLine[] = [
  { kind: "command", text: "autotarefas validate clientes.csv" },
  {
    kind: "plain",
    text: "Carregando schema: live_demo/backend/app/assets/schema_clientes.yaml",
  },
  { kind: "plain", text: "Schema carregado: 4 coluna(s) declarada(s)." },
  { kind: "plain", text: "Validando arquivo: clientes.csv" },
  { kind: "plain", text: "Encontrados 1 problema(s):" },
  { kind: "error", text: "Linha 6, coluna 'cpf': CPF invalido" },
  { kind: "ok", text: "Relatorio JSON salvo: out/validate_report.json" },
];

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [catalog, setCatalog] = useState<CatalogData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getHealth(), getCatalog()])
      .then(([h, c]) => {
        if (!cancelled) {
          setHealth(h);
          setCatalog(c);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "falha ao conectar");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const activeIds = useMemo(
    () => new Set(health?.active_automations ?? []),
    [health],
  );
  const online = !!health && (health.demo_servers[0]?.alive ?? false);
  const selectedAutomation = useMemo(
    () => catalog?.automations.find((a) => a.id === selectedId) ?? null,
    [catalog, selectedId],
  );

  const handleSelect = (id: string) => {
    setSelectedId(id);
    setTimeout(() => {
      document
        .getElementById("execucao")
        ?.scrollIntoView({ behavior: "smooth" });
    }, 150);
  };

  return (
    <div className="min-h-screen">
      <Navbar online={online} />
      <Hero health={health} />
      <StatusBar health={health} />
      <Catalog
        catalog={catalog}
        activeIds={activeIds}
        selectedId={selectedId}
        onSelect={handleSelect}
        loading={loading}
        error={error}
      />
      <ExecutionPanel selected={selectedAutomation} />
      <TerminalView lines={SAMPLE_LINES} sample />
      <Artifacts />
      <Footer />
    </div>
  );
}
