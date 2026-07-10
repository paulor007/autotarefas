import { useEffect, useMemo, useState } from "react";

import Artifacts from "./components/Artifacts";
import Catalog from "./components/Catalog";
import ExecutionPanel from "./components/ExecutionPanel";
import Footer from "./components/Footer";
import Hero from "./components/Hero";
import Navbar from "./components/Navbar";
import StatusBar from "./components/StatusBar";
import TerminalView, { type TerminalLine } from "./components/TerminalView";
import { useExecution } from "./hooks/useExecution";
import { useExtractReport } from "./hooks/useExtractReport";
import { useImportReport } from "./hooks/useImportReport";
import { useValidationReport } from "./hooks/useValidationReport";
import {
  getCatalog,
  getHealth,
  type Automation,
  type Catalog as CatalogData,
  type Health,
} from "./lib/api";

// Saida de exemplo: linhas reais representativas do stdout do AutoTarefas
// (Exportacao automatica de dados com o catalogo de demonstracao). Some na
// 1a execucao real, quando o terminal recebe o stdout ao vivo do SSE
// (/api/stream/{token}). A Exportacao e a origem do pipeline: puxa a base
// de um sistema, paginando, e gera os artefatos.
const SAMPLE_LINES: TerminalLine[] = [
  {
    kind: "command",
    text: "autotarefas extract api -u .../api/catalogo --out-dir saida/",
  },
  { kind: "plain", text: "Extraindo de http://.../api/catalogo" },
  { kind: "plain", text: "  Pagina 1/5 ... 10 registros (total: 10)" },
  { kind: "plain", text: "  Pagina 3/5 ... 10 registros (total: 30)" },
  { kind: "plain", text: "  Pagina 5/5 ... 7 registros (total: 47)" },
  { kind: "ok", text: "Extraidos 47 registros" },
  { kind: "ok", text: "[OK] Dados (CSV):    saida/dados_extraidos.csv" },
  { kind: "ok", text: "[OK] Dados (Excel):  saida/dados_extraidos.xlsx" },
  { kind: "ok", text: "[OK] Relatorio JSON: saida/extracao_report.json" },
  {
    kind: "done",
    text: "47 registros em 5 paginas -> prontos para a Auditoria de planilha",
  },
];

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [catalog, setCatalog] = useState<CatalogData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hasInteracted, setHasInteracted] = useState(false);

  const exec = useExecution();
  const validationReport = useValidationReport(exec.result);
  const importReport = useImportReport(exec.result);
  const extractReport = useExtractReport(exec.result);

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

  const handleRun = (
    automation: Automation,
    opts: { files?: File[]; useSample?: boolean },
  ) => {
    setHasInteracted(true);
    void exec.run(automation, opts);
    setTimeout(() => {
      document
        .getElementById("terminal")
        ?.scrollIntoView({ behavior: "smooth" });
    }, 150);
  };

  const terminalLines = hasInteracted ? exec.lines : SAMPLE_LINES;

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
      <ExecutionPanel
        selected={selectedAutomation}
        status={exec.status}
        error={exec.error}
        onRun={handleRun}
      />
      <TerminalView
        lines={terminalLines}
        status={exec.status}
        outcome={exec.result?.outcome}
        sample={!hasInteracted}
        onClear={hasInteracted ? exec.reset : undefined}
      />
      <Artifacts
        result={exec.result}
        report={validationReport}
        importReport={importReport}
        extractReport={extractReport}
        onNextStep={() => handleSelect("send_api")}
        onNextStepAudit={() => handleSelect("validate")}
      />
      <Footer />
    </div>
  );
}
